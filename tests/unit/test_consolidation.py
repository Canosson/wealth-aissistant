"""Unit tests for portfolio consolidation analytics (T031).

Tests the pure consolidate() function with known values — no DB, no network.
Covers: dedup, missing price, cross-currency FX, full fake-provider scenario (SC-002).
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from wealth_assistant.analytics.consolidation import (
    HoldingInput,
    SecurityInput,
    consolidate,
)

# ── Shared fixtures ────────────────────────────────────────────────────────────

AAPL_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
MSFT_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
SX5E_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")
USD_ACCT = uuid.UUID("00000000-0000-0000-0001-000000000001")
EUR_ACCT = uuid.UUID("00000000-0000-0000-0001-000000000002")

AAPL = SecurityInput(AAPL_ID, "AAPL", "Apple Inc.", "equity", "Technology", "USD")
MSFT = SecurityInput(MSFT_ID, "MSFT", "Microsoft", "equity", "Technology", "USD")
SX5E = SecurityInput(SX5E_ID, "SX5E", "Euro Stoxx 50 ETF", "etf", "Diversified", "EUR")


def _h(acct_id: uuid.UUID, acct_name: str, sec_id: uuid.UUID, qty: str) -> HoldingInput:
    return HoldingInput(acct_id, acct_name, sec_id, Decimal(qty))


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_single_holding_same_currency() -> None:
    result = consolidate(
        holdings=[_h(USD_ACCT, "USD Brokerage", AAPL_ID, "10")],
        securities={AAPL_ID: AAPL},
        latest_prices={AAPL_ID: Decimal("180.00")},
        fx_rates={},
        reporting_currency="USD",
    )
    assert result.total_value == Decimal("1800.00")
    assert len(result.holdings) == 1
    assert result.holdings[0].price_available is True
    assert result.holdings[0].quantity == Decimal("10")


def test_dedup_same_security_across_two_accounts() -> None:
    result = consolidate(
        holdings=[
            _h(USD_ACCT, "USD Brokerage", AAPL_ID, "10"),
            _h(EUR_ACCT, "EUR Brokerage", AAPL_ID, "5"),
        ],
        securities={AAPL_ID: AAPL},
        latest_prices={AAPL_ID: Decimal("180.00")},
        fx_rates={},
        reporting_currency="USD",
    )
    assert len(result.holdings) == 1, "same security must be consolidated to one entry"
    h = result.holdings[0]
    assert h.quantity == Decimal("15")
    assert result.total_value == Decimal("2700.00")
    assert set(h.accounts) == {"USD Brokerage", "EUR Brokerage"}


def test_missing_price_excluded_from_total() -> None:
    result = consolidate(
        holdings=[
            _h(USD_ACCT, "USD Brokerage", AAPL_ID, "10"),
            _h(USD_ACCT, "USD Brokerage", MSFT_ID, "20"),
        ],
        securities={AAPL_ID: AAPL, MSFT_ID: MSFT},
        latest_prices={AAPL_ID: Decimal("180.00")},  # MSFT price absent
        fx_rates={},
        reporting_currency="USD",
    )
    assert result.total_value == Decimal("1800.00")  # MSFT excluded (FR-012)
    msft = next(h for h in result.holdings if h.security_id == MSFT_ID)
    assert msft.price_available is False
    assert msft.value_amount is None


def test_cross_currency_holding_with_fx_rate() -> None:
    result = consolidate(
        holdings=[_h(EUR_ACCT, "EUR Brokerage", SX5E_ID, "50")],
        securities={SX5E_ID: SX5E},
        latest_prices={SX5E_ID: Decimal("90.00")},
        fx_rates={("EUR", "USD"): Decimal("1.10")},
        reporting_currency="USD",
    )
    # 50 × 90 × 1.10 = 4950
    assert result.total_value == Decimal("4950.00")
    assert result.holdings[0].price_available is True


def test_missing_fx_rate_treated_as_price_unavailable() -> None:
    result = consolidate(
        holdings=[_h(EUR_ACCT, "EUR Brokerage", SX5E_ID, "50")],
        securities={SX5E_ID: SX5E},
        latest_prices={SX5E_ID: Decimal("90.00")},
        fx_rates={},  # no EUR→USD rate
        reporting_currency="USD",
    )
    assert result.total_value == Decimal("0")
    assert result.holdings[0].price_available is False


def test_empty_holdings_returns_zero_total() -> None:
    result = consolidate(
        holdings=[],
        securities={},
        latest_prices={},
        fx_rates={},
        reporting_currency="USD",
    )
    assert result.total_value == Decimal("0")
    assert result.holdings == []


def test_full_fake_provider_portfolio_to_the_cent() -> None:
    """SC-002: consolidated total matches expected value to the cent."""
    holdings = [
        _h(USD_ACCT, "USD Brokerage", AAPL_ID, "10"),
        _h(EUR_ACCT, "EUR Brokerage", AAPL_ID, "5"),
        _h(USD_ACCT, "USD Brokerage", MSFT_ID, "20"),
        _h(EUR_ACCT, "EUR Brokerage", SX5E_ID, "50"),
    ]
    result = consolidate(
        holdings=holdings,
        securities={AAPL_ID: AAPL, MSFT_ID: MSFT, SX5E_ID: SX5E},
        latest_prices={
            AAPL_ID: Decimal("180.00"),
            MSFT_ID: Decimal("420.00"),
            SX5E_ID: Decimal("90.00"),
        },
        fx_rates={("EUR", "USD"): Decimal("1.10")},
        reporting_currency="USD",
    )
    # AAPL: 15×180=2700, MSFT: 20×420=8400, SX5E: 50×90×1.10=4950 → total=16050
    assert result.total_value == Decimal("16050.00")
    assert len(result.holdings) == 3
