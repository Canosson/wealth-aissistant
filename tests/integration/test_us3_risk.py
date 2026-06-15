"""T049: Integration tests for US3 — risk & diversification endpoint."""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import jwt as pyjwt
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from wealth_assistant.persistence.models import PortfolioSnapshot

_REG = {
    "email": "us3@example.com",
    "password": "s3cure-passw0rd!",
    "reporting_currency": "USD",
}


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _investor_id(token: str) -> uuid.UUID:
    payload = pyjwt.decode(token, options={"verify_signature": False})
    return uuid.UUID(payload["sub"])


@pytest_asyncio.fixture
async def investor_token(auth_client: AsyncClient) -> str:
    r = await auth_client.post("/auth/register", json=_REG)
    assert r.status_code == 201
    return r.json()["token"]


@pytest_asyncio.fixture
async def linked_investor(auth_client: AsyncClient, investor_token: str) -> str:
    await auth_client.post(
        "/connections", json={"public_token": "fake-pub"}, headers=_auth(investor_token)
    )
    return investor_token


@pytest_asyncio.fixture
async def investor_with_snapshots(
    auth_client: AsyncClient,
    linked_investor: str,
    db_session: AsyncSession,
) -> str:
    inv_id = _investor_id(linked_investor)
    base = date(2026, 1, 7)
    values = [10000, 10200, 10100, 10400, 10300]
    for i, v in enumerate(values):
        snap = PortfolioSnapshot(
            id=uuid.uuid4(),
            investor_id=inv_id,
            as_of=base + timedelta(weeks=i),
            total_value_amount=Decimal(str(v)),
            total_value_currency="USD",
            net_external_flow_amount=Decimal("0"),
        )
        db_session.add(snap)
    await db_session.commit()
    return linked_investor


class TestRiskEndpoint:
    async def test_risk_returns_200_shape(self, auth_client: AsyncClient, linked_investor: str):
        r = await auth_client.get("/portfolio/risk", headers=_auth(linked_investor))
        assert r.status_code == 200
        data = r.json()
        assert "hhi" in data
        assert "concentration" in data          # OpenAPI field name (not concentration_flags)
        assert "insufficient_history" in data
        assert "diversification" in data        # nested object per OpenAPI schema
        assert "summary" in data["diversification"]
        assert "asset_class_count" in data["diversification"]

    async def test_diversification_summary_non_empty(self, auth_client: AsyncClient, linked_investor: str):
        r = await auth_client.get("/portfolio/risk", headers=_auth(linked_investor))
        assert r.status_code == 200
        summary = r.json()["diversification"]["summary"]  # nested per OpenAPI schema
        assert isinstance(summary, str)
        assert len(summary) > 0

    async def test_risk_insufficient_history_without_snapshots(
        self, auth_client: AsyncClient, linked_investor: str
    ):
        r = await auth_client.get("/portfolio/risk", headers=_auth(linked_investor))
        assert r.status_code == 200
        assert r.json()["insufficient_history"] is True
        assert r.json()["annualized_volatility_pct"] is None  # OpenAPI field name

    async def test_risk_volatility_with_sufficient_snapshots(
        self, auth_client: AsyncClient, investor_with_snapshots: str
    ):
        r = await auth_client.get("/portfolio/risk", headers=_auth(investor_with_snapshots))
        assert r.status_code == 200
        data = r.json()
        assert data["insufficient_history"] is False
        assert data["annualized_volatility_pct"] is not None  # OpenAPI field name
        assert float(data["annualized_volatility_pct"]) > 0
