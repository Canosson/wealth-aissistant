"""T048: Unit tests for risk & diversification analytics."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from wealth_assistant.analytics.consolidation import ConsolidatedHolding, ConsolidatedPortfolio
from wealth_assistant.analytics.performance import SnapshotPoint
from wealth_assistant.analytics.risk import compute_risk

AAPL_ID = uuid.UUID("00000000-0000-0000-0000-000000000011")
BOND_ID = uuid.UUID("00000000-0000-0000-0000-000000000012")
CASH_ID = uuid.UUID("00000000-0000-0000-0000-000000000013")


def _holding(sec_id, asset_class, sector, value):
    return ConsolidatedHolding(
        security_id=sec_id,
        symbol="X",
        name="Test",
        asset_class=asset_class,
        sector=sector,
        quantity=Decimal("1"),
        value_amount=Decimal(str(value)),
        price_available=True,
        accounts=["acct"],
    )


def _portfolio(*holdings):
    total = sum(h.value_amount for h in holdings if h.price_available and h.value_amount)
    return ConsolidatedPortfolio(
        reporting_currency="USD",
        total_value=total,
        last_updated=None,
        stale=False,
        holdings=list(holdings),
    )


def _snapshot(as_of: date, value: float) -> SnapshotPoint:
    return SnapshotPoint(
        as_of=as_of,
        total_value=Decimal(str(value)),
        net_external_flow=Decimal("0"),
    )


# ── Concentration & HHI ──────────────────────────────────────────────────────

class TestConcentration:
    def test_hhi_two_equal_holdings(self):
        # Each 50% → HHI = 50² + 50² = 5000
        port = _portfolio(
            _holding(AAPL_ID, "equity", "tech", 1000),
            _holding(BOND_ID, "fixed_income", "govt", 1000),
        )
        result = compute_risk(port, [])
        assert result.hhi == Decimal("5000.00")

    def test_concentration_flag_dominant_holding(self):
        # AAPL at 75% → flagged
        port = _portfolio(
            _holding(AAPL_ID, "equity", "tech", 7500),
            _holding(BOND_ID, "fixed_income", "govt", 2500),
        )
        result = compute_risk(port, [])
        flagged_ids = {f.security_id for f in result.concentration_flags}
        assert AAPL_ID in flagged_ids
        aapl_flag = next(f for f in result.concentration_flags if f.security_id == AAPL_ID)
        assert aapl_flag.weight_pct == Decimal("75.00")

    def test_concentration_no_flags_below_threshold(self):
        # Ten equal holdings at 10% each → none flagged (threshold is ≥20%)
        port = _portfolio(*[_holding(uuid.uuid4(), "equity", "tech", 100) for _ in range(10)])
        result = compute_risk(port, [])
        assert result.concentration_flags == []

    def test_hhi_single_holding_is_max(self):
        port = _portfolio(_holding(AAPL_ID, "equity", "tech", 5000))
        result = compute_risk(port, [])
        assert result.hhi == Decimal("10000.00")


# ── Volatility ───────────────────────────────────────────────────────────────

class TestVolatility:
    def test_volatility_computed_with_sufficient_history(self):
        # 5 weekly snapshots → 4 returns → volatility computed
        snaps = [
            _snapshot(date(2026, 1, 7), 10000),
            _snapshot(date(2026, 1, 14), 10200),
            _snapshot(date(2026, 1, 21), 10100),
            _snapshot(date(2026, 1, 28), 10400),
            _snapshot(date(2026, 2, 4), 10300),
        ]
        port = _portfolio(_holding(AAPL_ID, "equity", "tech", 10300))
        result = compute_risk(port, snaps)
        assert result.insufficient_history is False
        assert result.volatility_pct is not None
        assert result.volatility_pct > Decimal("0")

    def test_volatility_insufficient_history_below_threshold(self):
        # 2 snapshots → below 4-snapshot threshold → insufficient
        snaps = [
            _snapshot(date(2026, 1, 7), 10000),
            _snapshot(date(2026, 1, 14), 10200),
        ]
        port = _portfolio(_holding(AAPL_ID, "equity", "tech", 10200))
        result = compute_risk(port, snaps)
        assert result.insufficient_history is True
        assert result.volatility_pct is None

    def test_volatility_zero_snapshots_is_insufficient(self):
        port = _portfolio(_holding(AAPL_ID, "equity", "tech", 10000))
        result = compute_risk(port, [])
        assert result.insufficient_history is True
        assert result.volatility_pct is None


# ── Diversification ──────────────────────────────────────────────────────────

class TestDiversification:
    def test_diversification_summary_non_empty(self):
        port = _portfolio(
            _holding(AAPL_ID, "equity", "tech", 1000),
            _holding(BOND_ID, "fixed_income", "govt", 1000),
        )
        result = compute_risk(port, [])
        assert isinstance(result.diversification_summary, str)
        assert len(result.diversification_summary) > 0

    def test_asset_class_count_correct(self):
        port = _portfolio(
            _holding(AAPL_ID, "equity", "tech", 1000),
            _holding(BOND_ID, "fixed_income", "govt", 1000),
            _holding(CASH_ID, "cash", None, 1000),
        )
        result = compute_risk(port, [])
        assert result.asset_class_count == 3
