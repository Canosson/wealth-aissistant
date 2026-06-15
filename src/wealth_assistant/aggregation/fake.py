"""In-memory fake aggregation provider — deterministic, offline, seeded (T021).

Seed: 2 accounts (USD brokerage + EUR brokerage) with overlapping AAPL holding
across both accounts so consolidation dedup is exercised in integration tests.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from wealth_assistant.aggregation.port import (
    LinkToken,
    ProviderAccount,
    ProviderConnection,
    ProviderHolding,
    ProviderSecurity,
)

_FIXED_ITEM_ID = "fake-item-001"
_FIXED_INSTITUTION = "Fake Bank & Brokerage"
_AS_OF = date(2026, 6, 12)

_ACCOUNTS: list[ProviderAccount] = [
    ProviderAccount(
        provider_account_id="fake-acct-usd",
        name="USD Brokerage",
        type="brokerage",
        currency="USD",
        cash_balance=Decimal("1000.00"),
    ),
    ProviderAccount(
        provider_account_id="fake-acct-eur",
        name="EUR Brokerage",
        type="brokerage",
        currency="EUR",
        cash_balance=Decimal("500.00"),
    ),
]

_HOLDINGS: list[ProviderHolding] = [
    ProviderHolding(
        provider_account_id="fake-acct-usd",
        security=ProviderSecurity(
            symbol="AAPL", name="Apple Inc.", asset_class="equity",
            sector="Technology", currency="USD",
        ),
        quantity=Decimal("10.0"), cost_basis=Decimal("1500.00"),
        price=Decimal("180.00"), as_of=_AS_OF,
    ),
    # Same security in EUR account — consolidation must dedup
    ProviderHolding(
        provider_account_id="fake-acct-eur",
        security=ProviderSecurity(
            symbol="AAPL", name="Apple Inc.", asset_class="equity",
            sector="Technology", currency="USD",
        ),
        quantity=Decimal("5.0"), cost_basis=None,
        price=Decimal("180.00"), as_of=_AS_OF,
    ),
    ProviderHolding(
        provider_account_id="fake-acct-usd",
        security=ProviderSecurity(
            symbol="MSFT", name="Microsoft Corporation", asset_class="equity",
            sector="Technology", currency="USD",
        ),
        quantity=Decimal("20.0"), cost_basis=Decimal("7000.00"),
        price=Decimal("420.00"), as_of=_AS_OF,
    ),
    ProviderHolding(
        provider_account_id="fake-acct-eur",
        security=ProviderSecurity(
            symbol="SX5E", name="Euro Stoxx 50 ETF", asset_class="etf",
            sector="Diversified", currency="EUR",
        ),
        quantity=Decimal("50.0"), cost_basis=Decimal("4000.00"),
        price=Decimal("90.00"), as_of=_AS_OF,
    ),
]


class FakeAggregationProvider:
    """Deterministic in-memory provider for tests and local development."""

    async def create_link_token(self, investor_id: uuid.UUID) -> LinkToken:
        return LinkToken(link_token=f"fake-link-token-{investor_id}")

    async def exchange_public_token(self, public_token: str) -> ProviderConnection:
        return ProviderConnection(
            provider_item_id=_FIXED_ITEM_ID,
            institution_name=_FIXED_INSTITUTION,
            access_ref="fake-access-ref-encrypted",
        )

    async def fetch_accounts(self, connection: ProviderConnection) -> list[ProviderAccount]:
        return list(_ACCOUNTS)

    async def fetch_holdings(self, connection: ProviderConnection) -> list[ProviderHolding]:
        return list(_HOLDINGS)
