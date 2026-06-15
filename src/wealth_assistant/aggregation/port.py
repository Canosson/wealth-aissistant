"""Aggregation provider port + DTOs (T020, contracts/internal-contracts.md)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol


# ── DTOs ──────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LinkToken:
    link_token: str


@dataclass(frozen=True)
class ProviderConnection:
    provider_item_id: str
    institution_name: str
    access_ref: str  # opaque encrypted handle — never returned to clients


@dataclass(frozen=True)
class ProviderAccount:
    provider_account_id: str
    name: str
    type: str  # "brokerage" | "cash" | "other"
    currency: str
    cash_balance: Decimal | None = None


@dataclass(frozen=True)
class ProviderSecurity:
    symbol: str | None
    name: str
    asset_class: str
    sector: str | None
    currency: str


@dataclass(frozen=True)
class ProviderHolding:
    provider_account_id: str
    security: ProviderSecurity
    quantity: Decimal
    cost_basis: Decimal | None
    price: Decimal | None
    as_of: date


# ── Error types ───────────────────────────────────────────────────────────────

class ProviderAuthError(Exception):
    """Credentials revoked or MFA required."""


class ProviderUnavailableError(Exception):
    """Transient outage or timeout."""


class ProviderUnsupportedError(Exception):
    """Institution or account type not supported."""


# ── Port (Protocol) ───────────────────────────────────────────────────────────

class AggregationProvider(Protocol):
    """Abstract port — all concrete adapters implement this interface."""

    async def create_link_token(self, investor_id: uuid.UUID) -> LinkToken:
        """Begin a linking session."""
        ...

    async def exchange_public_token(self, public_token: str) -> ProviderConnection:
        """Complete linking; returns an opaque connection handle."""
        ...

    async def fetch_accounts(
        self, connection: ProviderConnection
    ) -> list[ProviderAccount]:
        """Retrieve accounts for an established connection."""
        ...

    async def fetch_holdings(
        self, connection: ProviderConnection
    ) -> list[ProviderHolding]:
        """Retrieve holdings/positions for an established connection."""
        ...
