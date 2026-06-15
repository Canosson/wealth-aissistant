"""T039: Unit tests for allocation and performance analytics."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from wealth_assistant.analytics.consolidation import ConsolidatedHolding, ConsolidatedPortfolio

AAPL_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
BOND_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
UNK_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")


def _holding(sec_id, asset_class, sector, value, accounts=None):
    return ConsolidatedHolding(
        security_id=sec_id,
        symbol="X",
        name="Test",
        asset_class=asset_class,
        sector=sector,
        quantity=Decimal("1"),
        value_amount=Decimal(str(value)),
        price_available=True,
        accounts=accounts or ["acct"],
    )


def _no_price(sec_id):
    return ConsolidatedHolding(
        security_id=sec_id,
        symbol=None,
        name="Unknown",
        asset_class="equity",
        sector=None,
        quantity=Decimal("1"),
        value_amount=None,
        price_available=False,
        accounts=["acct"],
    )


def _portfolio(*holdings):
    total = sum(
        (h.value_amount or Decimal("0")) for h in holdings if h.price_available and h.value_amount
    )
    return ConsolidatedPortfolio(
        reporting_currency="USD",
        total_value=total,
        holdings=list(holdings),
    )


# ── Allocation ──────────────────────────────────────────────────────────────

class TestAllocation:
    def test_asset_class_weights_sum_to_100(self):
        from wealth_assistant.analytics.allocation import allocate
        port = _portfolio(
            _holding(AAPL_ID, "equity", "Technology", 7500),
            _holding(BOND_ID, "fixed_income", "Government", 2500),
        )
        result = allocate(port, by="asset_class")
        total_pct = sum(s.weight_pct for s in result.slices)
        assert total_pct == Decimal("100")

    def test_asset_class_values_correct(self):
        from wealth_assistant.analytics.allocation import allocate
        port = _portfolio(
            _holding(AAPL_ID, "equity", "Technology", 7500),
            _holding(BOND_ID, "fixed_income", "Government", 2500),
        )
        result = allocate(port, by="asset_class")
        equity = next(s for s in result.slices if s.label == "equity")
        assert equity.weight_pct == Decimal("75.00")

    def test_unclassified_asset_class_gets_unclassified_label(self):
        from wealth_assistant.analytics.allocation import allocate
        port = _portfolio(
            _holding(AAPL_ID, "equity", "Technology", 8000),
            _holding(UNK_ID, "unclassified", None, 2000),
        )
        result = allocate(port, by="asset_class")
        labels = [s.label for s in result.slices]
        assert "Unclassified" in labels
        total_pct = sum(s.weight_pct for s in result.slices)
        assert total_pct == Decimal("100")

    def test_null_sector_grouped_as_unclassified(self):
        from wealth_assistant.analytics.allocation import allocate
        port = _portfolio(
            _holding(AAPL_ID, "equity", "Technology", 6000),
            _holding(BOND_ID, "fixed_income", None, 4000),
        )
        result = allocate(port, by="sector")
        labels = [s.label for s in result.slices]
        assert "Unclassified" in labels

    def test_no_price_holdings_excluded(self):
        from wealth_assistant.analytics.allocation import allocate
        port = _portfolio(
            _holding(AAPL_ID, "equity", "Technology", 10000),
            _no_price(BOND_ID),
        )
        result = allocate(port, by="asset_class")
        total_pct = sum(s.weight_pct for s in result.slices)
        assert total_pct == Decimal("100")
        assert len(result.slices) == 1

    def test_by_field_reflected(self):
        from wealth_assistant.analytics.allocation import allocate
        port = _portfolio(_holding(AAPL_ID, "equity", "Technology", 10000))
        assert allocate(port, by="sector").by == "sector"
        assert allocate(port, by="asset_class").by == "asset_class"


# ── Performance ─────────────────────────────────────────────────────────────

class TestPerformance:
    def test_period_return_hand_calc(self):
        from wealth_assistant.analytics.performance import SnapshotPoint, compute_performance
        snapshots = [
            SnapshotPoint(as_of=date(2026, 1, 1), total_value=Decimal("10000"), net_external_flow=Decimal("0")),
            SnapshotPoint(as_of=date(2026, 2, 1), total_value=Decimal("10500"), net_external_flow=Decimal("0")),
        ]
        result = compute_performance(snapshots, period="ALL", reporting_currency="USD", as_of_date=date(2026, 2, 1))
        assert not result.insufficient_history
        assert result.return_pct == Decimal("5.00")
        assert result.gain_loss == Decimal("500.00")

    def test_net_flow_subtracted(self):
        from wealth_assistant.analytics.performance import SnapshotPoint, compute_performance
        snapshots = [
            SnapshotPoint(as_of=date(2026, 1, 1), total_value=Decimal("10000"), net_external_flow=Decimal("0")),
            SnapshotPoint(as_of=date(2026, 2, 1), total_value=Decimal("11000"), net_external_flow=Decimal("500")),
        ]
        result = compute_performance(snapshots, period="ALL", reporting_currency="USD", as_of_date=date(2026, 2, 1))
        assert not result.insufficient_history
        assert result.return_pct == Decimal("5.00")
        assert result.gain_loss == Decimal("500.00")

    def test_insufficient_history_empty(self):
        from wealth_assistant.analytics.performance import compute_performance
        result = compute_performance([], period="1M", reporting_currency="USD", as_of_date=date(2026, 2, 1))
        assert result.insufficient_history

    def test_insufficient_history_one_snapshot(self):
        from wealth_assistant.analytics.performance import SnapshotPoint, compute_performance
        snapshots = [
            SnapshotPoint(as_of=date(2026, 2, 1), total_value=Decimal("10000"), net_external_flow=Decimal("0")),
        ]
        result = compute_performance(snapshots, period="ALL", reporting_currency="USD", as_of_date=date(2026, 2, 1))
        assert result.insufficient_history

    def test_period_field_set(self):
        from wealth_assistant.analytics.performance import SnapshotPoint, compute_performance
        snapshots = [
            SnapshotPoint(as_of=date(2026, 1, 1), total_value=Decimal("10000"), net_external_flow=Decimal("0")),
            SnapshotPoint(as_of=date(2026, 2, 1), total_value=Decimal("10500"), net_external_flow=Decimal("0")),
        ]
        result = compute_performance(snapshots, period="1M", reporting_currency="USD", as_of_date=date(2026, 2, 1))
        assert result.period == "1M"

    def test_period_1m_boundary_no_start_snapshot(self):
        from wealth_assistant.analytics.performance import SnapshotPoint, compute_performance
        # 1M boundary from Feb 1 = Jan 2. Earliest snapshot is Jan 15 (after Jan 2) → no start → insufficient
        snapshots = [
            SnapshotPoint(as_of=date(2026, 1, 15), total_value=Decimal("10000"), net_external_flow=Decimal("0")),
            SnapshotPoint(as_of=date(2026, 2, 1), total_value=Decimal("10500"), net_external_flow=Decimal("0")),
        ]
        result = compute_performance(snapshots, period="1M", reporting_currency="USD", as_of_date=date(2026, 2, 1))
        assert result.insufficient_history
