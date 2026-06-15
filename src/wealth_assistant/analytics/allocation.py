"""T041: Allocation analytics — pure functions, no I/O.

Groups a consolidated portfolio's holdings by asset_class, sector, or account.
Weights are in percent (0–100) and sum to exactly 100 (last slice absorbs rounding).
Holdings with unavailable prices are excluded. Null/unclassified keys become "Unclassified".
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from wealth_assistant.analytics.consolidation import ConsolidatedPortfolio

_UNCLASSIFIED = "Unclassified"
_TWO_DP = Decimal("0.01")


@dataclass(frozen=True)
class AllocationSlice:
    label: str
    weight_pct: Decimal  # 0–100 with 2 dp; slices sum to 100
    value: Decimal       # in portfolio's reporting currency


@dataclass(frozen=True)
class AllocationResult:
    by: str
    slices: list[AllocationSlice]


def allocate(portfolio: ConsolidatedPortfolio, by: str = "asset_class") -> AllocationResult:
    buckets: dict[str, Decimal] = defaultdict(Decimal)

    for h in portfolio.holdings:
        if not h.price_available or h.value_amount is None:
            continue
        keys = _keys_for(h, by)
        if not keys:
            buckets[_UNCLASSIFIED] += h.value_amount
        else:
            per_key = h.value_amount / len(keys)
            for key in keys:
                buckets[key] += per_key

    total = sum(buckets.values(), Decimal("0"))
    if total == Decimal("0"):
        return AllocationResult(by=by, slices=[])

    labels = sorted(buckets.keys())
    raw_pcts = [buckets[lbl] / total * Decimal("100") for lbl in labels]
    rounded = [p.quantize(_TWO_DP, rounding=ROUND_HALF_UP) for p in raw_pcts]

    # Adjust last slice so sum is exactly 100
    diff = Decimal("100") - sum(rounded)
    if rounded:
        rounded[-1] += diff

    slices = [
        AllocationSlice(label=lbl, weight_pct=pct, value=buckets[lbl].quantize(_TWO_DP))
        for lbl, pct in zip(labels, rounded)
    ]
    return AllocationResult(by=by, slices=slices)


def _keys_for(h, by: str) -> list[str]:
    if by == "asset_class":
        cls = h.asset_class
        return [_UNCLASSIFIED] if (cls is None or cls == "unclassified") else [cls]
    if by == "sector":
        return [_UNCLASSIFIED] if h.sector is None else [h.sector]
    if by == "account":
        return list(h.accounts) if h.accounts else [_UNCLASSIFIED]
    return [_UNCLASSIFIED]
