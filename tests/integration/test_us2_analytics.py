"""T040: Integration tests for US2 — allocation & performance endpoints.

Uses the fake aggregation provider (offline, deterministic).
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import jwt as pyjwt
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from wealth_assistant.persistence.models import FxRate, PortfolioSnapshot

_REG = {
    "email": "us2@example.com",
    "password": "s3cure-passw0rd!",
    "reporting_currency": "USD",
}
_AS_OF = date(2026, 6, 12)


@pytest_asyncio.fixture
async def investor_token(auth_client: AsyncClient) -> str:
    r = await auth_client.post("/auth/register", json=_REG)
    assert r.status_code == 201
    return r.json()["token"]


@pytest_asyncio.fixture
async def eur_usd_fx(db_session: AsyncSession) -> None:
    fx = FxRate(
        id=uuid.uuid4(),
        base_currency="EUR",
        quote_currency="USD",
        rate=Decimal("1.10"),
        as_of=_AS_OF,
    )
    db_session.add(fx)
    await db_session.commit()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _investor_id(token: str) -> uuid.UUID:
    payload = pyjwt.decode(token, options={"verify_signature": False})
    return uuid.UUID(payload["sub"])


@pytest.mark.asyncio
async def test_allocation_slices_sum_to_100(
    auth_client: AsyncClient,
    investor_token: str,
    eur_usd_fx: None,
) -> None:
    """After linking fake accounts, allocation by asset_class sums to 100%."""
    await auth_client.post(
        "/connections", json={"public_token": "fake-pub"}, headers=_auth(investor_token)
    )
    r = await auth_client.get("/portfolio/allocation", headers=_auth(investor_token))
    assert r.status_code == 200
    data = r.json()
    assert data["by"] == "asset_class"
    assert len(data["slices"]) > 0
    total_pct = sum(Decimal(s["weight_pct"]) for s in data["slices"])
    assert total_pct == Decimal("100")


@pytest.mark.asyncio
async def test_allocation_by_sector(
    auth_client: AsyncClient,
    investor_token: str,
    eur_usd_fx: None,
) -> None:
    """by=sector query param is honoured."""
    await auth_client.post(
        "/connections", json={"public_token": "fake-pub"}, headers=_auth(investor_token)
    )
    r = await auth_client.get("/portfolio/allocation?by=sector", headers=_auth(investor_token))
    assert r.status_code == 200
    assert r.json()["by"] == "sector"


@pytest.mark.asyncio
async def test_performance_insufficient_history_no_snapshots(
    auth_client: AsyncClient,
    investor_token: str,
    eur_usd_fx: None,
) -> None:
    """No snapshots → insufficient_history=true regardless of period."""
    await auth_client.post(
        "/connections", json={"public_token": "fake-pub"}, headers=_auth(investor_token)
    )
    r = await auth_client.get("/portfolio/performance?period=1M", headers=_auth(investor_token))
    assert r.status_code == 200
    data = r.json()
    assert data["insufficient_history"] is True


@pytest.mark.asyncio
async def test_performance_with_two_snapshots(
    auth_client: AsyncClient,
    investor_token: str,
    db_session: AsyncSession,
    eur_usd_fx: None,
) -> None:
    """With two snapshots, ALL-period return matches hand calculation."""
    inv_id = _investor_id(investor_token)

    snap1 = PortfolioSnapshot(
        id=uuid.uuid4(),
        investor_id=inv_id,
        as_of=date(2026, 1, 1),
        total_value_amount=Decimal("10000"),
        total_value_currency="USD",
        net_external_flow_amount=Decimal("0"),
    )
    snap2 = PortfolioSnapshot(
        id=uuid.uuid4(),
        investor_id=inv_id,
        as_of=date(2026, 2, 1),
        total_value_amount=Decimal("10500"),
        total_value_currency="USD",
        net_external_flow_amount=Decimal("0"),
    )
    db_session.add(snap1)
    db_session.add(snap2)
    await db_session.commit()

    r = await auth_client.get("/portfolio/performance?period=ALL", headers=_auth(investor_token))
    assert r.status_code == 200
    data = r.json()
    assert data["insufficient_history"] is False
    assert data["return_pct"] == "5.00"
    assert data["gain_loss"]["amount"] == "500.00"
