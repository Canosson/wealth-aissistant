"""T042: Performance analytics — pure functions, no I/O.

Computes simple period return from PortfolioSnapshot history:
  return = (end_value - start_value - net_external_flows) / start_value

Period determines the start boundary; "insufficient history" when no qualifying
snapshots exist for the requested window.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class SnapshotPoint:
    as_of: date
    total_value: Decimal
    net_external_flow: Decimal  # deposits/withdrawals recorded on this snapshot date


@dataclass
class PerformanceResult:
    period: str
    return_pct: Decimal
    gain_loss: Decimal
    start_value: Decimal
    end_value: Decimal
    insufficient_history: bool
    currency: str


_TWO_DP = Decimal("0.01")

_PERIOD_DAYS: dict[str, int | None] = {
    "1M": 30,
    "3M": 90,
    "6M": 180,
    "1Y": 365,
    "ALL": None,
    "YTD": -1,  # sentinel: Jan 1 of as_of year
}


def _insufficient(period: str, currency: str) -> PerformanceResult:
    zero = Decimal("0.00")
    return PerformanceResult(
        period=period,
        return_pct=zero,
        gain_loss=zero,
        start_value=zero,
        end_value=zero,
        insufficient_history=True,
        currency=currency,
    )


def compute_performance(
    snapshots: list[SnapshotPoint],
    period: str,
    reporting_currency: str,
    as_of_date: date,
) -> PerformanceResult:
    if len(snapshots) < 2:
        return _insufficient(period, reporting_currency)

    ordered = sorted(snapshots, key=lambda s: s.as_of)

    # End snapshot: most recent at or before as_of_date
    end_candidates = [s for s in ordered if s.as_of <= as_of_date]
    if not end_candidates:
        return _insufficient(period, reporting_currency)
    end = end_candidates[-1]

    # Start snapshot based on period
    if period == "ALL":
        start_candidates = [s for s in ordered if s.as_of < end.as_of]
        if not start_candidates:
            return _insufficient(period, reporting_currency)
        start = start_candidates[0]
    elif period == "YTD":
        boundary = date(as_of_date.year, 1, 1)
        start_candidates = [s for s in ordered if s.as_of <= boundary and s.as_of < end.as_of]
        if not start_candidates:
            return _insufficient(period, reporting_currency)
        start = start_candidates[-1]
    else:
        days = _PERIOD_DAYS.get(period, 30)
        boundary = as_of_date - timedelta(days=days)
        start_candidates = [s for s in ordered if s.as_of <= boundary]
        if not start_candidates:
            return _insufficient(period, reporting_currency)
        start = start_candidates[-1]

    # Accumulate net external flows between start (exclusive) and end (inclusive)
    net_flows = sum(
        (s.net_external_flow for s in ordered if start.as_of < s.as_of <= end.as_of),
        Decimal("0"),
    )

    if start.total_value == Decimal("0"):
        return _insufficient(period, reporting_currency)

    gain_loss = end.total_value - start.total_value - net_flows
    return_pct = (gain_loss / start.total_value * Decimal("100")).quantize(
        _TWO_DP, rounding=ROUND_HALF_UP
    )

    return PerformanceResult(
        period=period,
        return_pct=return_pct,
        gain_loss=gain_loss.quantize(_TWO_DP),
        start_value=start.total_value.quantize(_TWO_DP),
        end_value=end.total_value.quantize(_TWO_DP),
        insufficient_history=False,
        currency=reporting_currency,
    )
