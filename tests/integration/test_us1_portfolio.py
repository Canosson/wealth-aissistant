"""Integration tests for US1: link accounts + consolidated portfolio (T032).

Runs against the fake aggregation provider (offline, deterministic).
Covers: link, consolidate to the cent (SC-002), dedup (FR-004), refresh, unlink.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from wealth_assistant.persistence.models import FxRate

_REG = {
    "email": "us1@example.com",
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
    """Insert EUR/USD FX rate so SX5E (EUR-quoted) can be valued in USD."""
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


@pytest.mark.asyncio
async def test_link_one_account_portfolio_has_usd_holdings(
    auth_client: AsyncClient,
    investor_token: str,
    eur_usd_fx: None,
) -> None:
    await auth_client.post(
        "/connections", json={"public_token": "fake-pub"}, headers=_auth(investor_token)
    )
    r = await auth_client.get("/portfolio", headers=_auth(investor_token))
    assert r.status_code == 200
    symbols = {h["symbol"] for h in r.json()["holdings"]}
    assert "AAPL" in symbols
    assert "MSFT" in symbols


@pytest.mark.asyncio
async def test_link_two_accounts_dedup_aapl(
    auth_client: AsyncClient,
    investor_token: str,
    eur_usd_fx: None,
) -> None:
    """AAPL in two accounts must appear once (FR-004) with combined quantity."""
    await auth_client.post(
        "/connections", json={"public_token": "fake-pub"}, headers=_auth(investor_token)
    )
    r = await auth_client.get("/portfolio", headers=_auth(investor_token))
    aapl_entries = [h for h in r.json()["holdings"] if h["symbol"] == "AAPL"]
    assert len(aapl_entries) == 1
    assert Decimal(aapl_entries[0]["quantity"]) == Decimal("15")
    assert len(aapl_entries[0]["accounts"]) == 2


@pytest.mark.asyncio
async def test_portfolio_total_matches_expected_to_the_cent(
    auth_client: AsyncClient,
    investor_token: str,
    eur_usd_fx: None,
) -> None:
    """SC-002: total == AAPL(15×$180) + MSFT(20×$420) + SX5E(50×€90×1.10) = $16,050."""
    await auth_client.post(
        "/connections", json={"public_token": "fake-pub"}, headers=_auth(investor_token)
    )
    r = await auth_client.get("/portfolio", headers=_auth(investor_token))
    total = Decimal(r.json()["total_value"]["amount"])
    assert total == Decimal("16050.00")


@pytest.mark.asyncio
async def test_refresh_updates_last_synced_at(
    auth_client: AsyncClient,
    investor_token: str,
    eur_usd_fx: None,
) -> None:
    conn = await auth_client.post(
        "/connections", json={"public_token": "fake-pub"}, headers=_auth(investor_token)
    )
    conn_id = conn.json()["id"]
    r = await auth_client.post(f"/connections/{conn_id}/refresh", headers=_auth(investor_token))
    assert r.status_code == 200
    assert r.json()["last_synced_at"] is not None


@pytest.mark.asyncio
async def test_unlink_removes_holdings_and_zeroes_total(
    auth_client: AsyncClient,
    investor_token: str,
    eur_usd_fx: None,
) -> None:
    conn = await auth_client.post(
        "/connections", json={"public_token": "fake-pub"}, headers=_auth(investor_token)
    )
    conn_id = conn.json()["id"]

    before = await auth_client.get("/portfolio", headers=_auth(investor_token))
    assert len(before.json()["holdings"]) > 0

    await auth_client.delete(f"/connections/{conn_id}", headers=_auth(investor_token))

    after = await auth_client.get("/portfolio", headers=_auth(investor_token))
    assert after.json()["holdings"] == []
    assert Decimal(after.json()["total_value"]["amount"]) == Decimal("0")
