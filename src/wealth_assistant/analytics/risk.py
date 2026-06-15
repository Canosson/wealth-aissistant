"""Risk & diversification analytics (T050, US3)."""
from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from wealth_assistant.analytics.consolidation import ConsolidatedPortfolio
from wealth_assistant.analytics.performance import SnapshotPoint

_CONCENTRATION_THRESHOLD = Decimal("20")
_MIN_WEEKLY_SNAPSHOTS = 4
_TWO_DP = Decimal("0.01")


@dataclass(frozen=True)
class ConcentrationFlag:
    security_id: UUID
    symbol: str | None
    name: str | None
    weight_pct: Decimal


@dataclass
class RiskResult:
    hhi: Decimal
    concentration_flags: list[ConcentrationFlag]
    volatility_pct: Decimal | None
    insufficient_history: bool
    diversification_summary: str
    asset_class_count: int
    sector_count: int


def compute_risk(
    portfolio: ConsolidatedPortfolio,
    snapshots: list[SnapshotPoint],
) -> RiskResult:
    priced = [
        h for h in portfolio.holdings
        if h.price_available and h.value_amount is not None
    ]
    total = sum((h.value_amount for h in priced), Decimal("0"))

    hhi = Decimal("0")
    concentration_flags: list[ConcentrationFlag] = []

    if total > 0:
        for h in priced:
            weight_pct = (h.value_amount / total * 100).quantize(_TWO_DP)
            hhi += weight_pct ** 2
            if weight_pct >= _CONCENTRATION_THRESHOLD:
                concentration_flags.append(
                    ConcentrationFlag(
                        security_id=h.security_id,
                        symbol=h.symbol,
                        name=h.name,
                        weight_pct=weight_pct,
                    )
                )

    hhi = hhi.quantize(_TWO_DP)

    insufficient_history = len(snapshots) < _MIN_WEEKLY_SNAPSHOTS
    volatility_pct: Decimal | None = None

    if not insufficient_history:
        sorted_snaps = sorted(snapshots, key=lambda s: s.as_of)
        returns: list[float] = []
        for i in range(1, len(sorted_snaps)):
            prev = sorted_snaps[i - 1].total_value
            curr = sorted_snaps[i].total_value
            if prev > 0:
                returns.append(float((curr - prev) / prev))

        if len(returns) >= 2:
            n = len(returns)
            mean = sum(returns) / n
            variance = sum((r - mean) ** 2 for r in returns) / (n - 1)
            weekly_std = math.sqrt(variance)
            volatility_pct = Decimal(str(round(weekly_std * math.sqrt(52) * 100, 2)))

    asset_classes = {
        h.asset_class
        for h in priced
        if h.asset_class and h.asset_class.lower() != "unclassified"
    }
    sectors = {h.sector for h in priced if h.sector}

    ac_count = len(asset_classes) if asset_classes else (1 if priced else 0)
    sec_count = len(sectors)

    if not priced or total == 0:
        summary = "No priced holdings to assess."
    elif ac_count >= 3:
        summary = f"Diversified across {ac_count} asset classes."
    elif ac_count == 2:
        summary = "Moderately diversified across 2 asset classes."
    else:
        summary = "Concentrated in 1 asset class. Consider diversifying."

    return RiskResult(
        hhi=hhi,
        concentration_flags=concentration_flags,
        volatility_pct=volatility_pct,
        insufficient_history=insufficient_history,
        diversification_summary=summary,
        asset_class_count=ac_count,
        sector_count=sec_count,
    )
