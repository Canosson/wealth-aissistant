"""P1 #4: End-to-end Plaid sandbox validation.

Skipped automatically when PLAID_CLIENT_ID / PLAID_SECRET are absent or
AGGREGATION_PROVIDER != 'plaid', so the regular test suite (which uses the
fake adapter) is unaffected.

Run locally with real credentials:
    AGGREGATION_PROVIDER=plaid uv run pytest tests/integration/test_plaid_adapter.py -v

Add PLAID_CLIENT_ID + PLAID_SECRET to GitHub secrets to run in CI.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from wealth_assistant.aggregation.plaid_adapter import PlaidAdapter, _make_client
from wealth_assistant.aggregation.port import (
    LinkToken,
    ProviderAccount,
    ProviderConnection,
    ProviderHolding,
    ProviderUnavailableError,
)
from wealth_assistant.config import get_settings

# ---------------------------------------------------------------------------
# Skip guard — all tests in this module require live Plaid sandbox credentials
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.skipif(
    not (
        (s := get_settings()).plaid_client_id
        and s.plaid_secret
        and s.aggregation_provider == "plaid"
    ),
    reason="Plaid sandbox credentials not configured (set AGGREGATION_PROVIDER=plaid + PLAID_CLIENT_ID + PLAID_SECRET)",
)

# ---------------------------------------------------------------------------
# Sandbox fixture: creates a real access_token via public_token/create bypass
# ---------------------------------------------------------------------------

SANDBOX_INSTITUTION = "ins_109508"  # First Platypus Bank — supports investments


@pytest.fixture(scope="module")
def plaid_connection() -> ProviderConnection:
    """Exchange a sandbox public_token for a real access_token once per module."""
    from plaid.model.products import Products
    from plaid.model.sandbox_public_token_create_request import SandboxPublicTokenCreateRequest

    client = _make_client()
    resp = client.sandbox_public_token_create(
        SandboxPublicTokenCreateRequest(
            institution_id=SANDBOX_INSTITUTION,
            initial_products=[Products("investments")],
        )
    )
    from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest

    ex = client.item_public_token_exchange(
        ItemPublicTokenExchangeRequest(public_token=resp.public_token)
    )
    return ProviderConnection(
        provider_item_id=ex.item_id,
        institution_name="First Platypus Bank (sandbox)",
        access_ref=ex.access_token,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_link_token_returns_token():
    adapter = PlaidAdapter()
    lt = await adapter.create_link_token(uuid.uuid4())
    assert isinstance(lt, LinkToken)
    assert lt.link_token.startswith("link-sandbox-")


@pytest.mark.asyncio
async def test_exchange_public_token_returns_connection():
    from plaid.model.products import Products
    from plaid.model.sandbox_public_token_create_request import SandboxPublicTokenCreateRequest

    client = _make_client()
    pub = client.sandbox_public_token_create(
        SandboxPublicTokenCreateRequest(
            institution_id=SANDBOX_INSTITUTION,
            initial_products=[Products("investments")],
        )
    )
    adapter = PlaidAdapter()
    conn = await adapter.exchange_public_token(pub.public_token)
    assert isinstance(conn, ProviderConnection)
    assert conn.access_ref.startswith("access-sandbox-")
    assert conn.provider_item_id


@pytest.mark.asyncio
async def test_fetch_accounts_returns_list(plaid_connection: ProviderConnection):
    adapter = PlaidAdapter()
    accounts = await adapter.fetch_accounts(plaid_connection)
    assert len(accounts) > 0
    for a in accounts:
        assert isinstance(a, ProviderAccount)
        assert a.name
        assert a.type in ("brokerage", "cash", "other")
        assert a.currency


@pytest.mark.asyncio
async def test_fetch_accounts_includes_brokerage(plaid_connection: ProviderConnection):
    adapter = PlaidAdapter()
    accounts = await adapter.fetch_accounts(plaid_connection)
    types = {a.type for a in accounts}
    assert "brokerage" in types, f"Expected brokerage account; got types: {types}"


@pytest.mark.asyncio
async def test_fetch_holdings_returns_list(plaid_connection: ProviderConnection):
    adapter = PlaidAdapter()
    holdings = await adapter.fetch_holdings(plaid_connection)
    assert len(holdings) > 0
    for h in holdings:
        assert isinstance(h, ProviderHolding)
        assert isinstance(h.quantity, Decimal)
        assert h.quantity > 0
        assert h.security.name
        assert h.security.asset_class


@pytest.mark.asyncio
async def test_fetch_holdings_asset_classes_are_valid(plaid_connection: ProviderConnection):
    valid = {"equity", "etf", "fund", "fixed_income", "cash", "crypto", "other"}
    adapter = PlaidAdapter()
    holdings = await adapter.fetch_holdings(plaid_connection)
    for h in holdings:
        assert h.security.asset_class in valid, (
            f"Unexpected asset_class '{h.security.asset_class}' for {h.security.name}"
        )


@pytest.mark.asyncio
async def test_invalid_access_token_raises_provider_unavailable():
    adapter = PlaidAdapter()
    bad_conn = ProviderConnection(
        provider_item_id="fake-item",
        institution_name="nowhere",
        access_ref="access-sandbox-00000000-0000-0000-0000-000000000000",
    )
    with pytest.raises(ProviderUnavailableError):
        await adapter.fetch_accounts(bad_conn)
