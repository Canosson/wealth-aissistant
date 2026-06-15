"""Portfolio consolidation analytics — pure functions, no I/O (T033).

Deduplicates holdings of the same security across multiple accounts, values
each in the reporting currency, and excludes holdings with unavailable prices
or FX rates from the total (FR-012).
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class HoldingInput:
    account_id: uuid.UUID
    account_name: str
    security_id: uuid.UUID
    quantity: Decimal


@dataclass(frozen=True)
class SecurityInput:
    id: uuid.UUID
    symbol: str | None
    name: str
    asset_class: str
    sector: str | None
    currency: str  # ISO-4217 quote currency of the security's price


@dataclass(frozen=True)
class ConsolidatedHolding:
    security_id: uuid.UUID
    symbol: str | None
    name: str
    asset_class: str
    sector: str | None
    quantity: Decimal
    value_amount: Decimal | None  # in reporting currency; None when price unavailable
    price_available: bool
    accounts: list[str]
    # Valuation inputs retained so snapshots can freeze them (reproducibility, R6)
    price_amount: Decimal | None = None  # in the security's native currency
    price_currency: str | None = None
    fx_rate: Decimal = Decimal("1")  # native → reporting multiplier used


@dataclass
class ConsolidatedPortfolio:
    reporting_currency: str
    total_value: Decimal
    holdings: list[ConsolidatedHolding] = field(default_factory=list)
    last_updated: datetime | None = None
    stale: bool = False


def consolidate(
    holdings: list[HoldingInput],
    securities: dict[uuid.UUID, SecurityInput],
    latest_prices: dict[uuid.UUID, Decimal],  # security_id → price in security's currency
    fx_rates: dict[tuple[str, str], Decimal],  # (base, quote) → multiplier
    reporting_currency: str,
    last_updated: datetime | None = None,
    stale: bool = False,
) -> ConsolidatedPortfolio:
    grouped: dict[uuid.UUID, list[HoldingInput]] = defaultdict(list)
    for h in holdings:
        grouped[h.security_id].append(h)

    result: list[ConsolidatedHolding] = []
    total = Decimal("0")

    for sec_id, sec_holdings in grouped.items():
        security = securities[sec_id]
        total_qty = sum((h.quantity for h in sec_holdings), Decimal("0"))
        account_names = [h.account_name for h in sec_holdings]

        price = latest_prices.get(sec_id)
        if price is None:
            result.append(ConsolidatedHolding(
                security_id=sec_id,
                symbol=security.symbol,
                name=security.name,
                asset_class=security.asset_class,
                sector=security.sector,
                quantity=total_qty,
                value_amount=None,
                price_available=False,
                accounts=account_names,
            ))
            continue

        value_native = total_qty * price
        rate_used = Decimal("1")
        if security.currency == reporting_currency:
            value_reporting = value_native
        else:
            rate = fx_rates.get((security.currency, reporting_currency))
            if rate is None:
                result.append(ConsolidatedHolding(
                    security_id=sec_id,
                    symbol=security.symbol,
                    name=security.name,
                    asset_class=security.asset_class,
                    sector=security.sector,
                    quantity=total_qty,
                    value_amount=None,
                    price_available=False,
                    accounts=account_names,
                ))
                continue
            value_reporting = value_native * rate
            rate_used = rate

        total += value_reporting
        result.append(ConsolidatedHolding(
            security_id=sec_id,
            symbol=security.symbol,
            name=security.name,
            asset_class=security.asset_class,
            sector=security.sector,
            quantity=total_qty,
            value_amount=value_reporting,
            price_available=True,
            accounts=account_names,
            price_amount=price,
            price_currency=security.currency,
            fx_rate=rate_used,
        ))

    return ConsolidatedPortfolio(
        reporting_currency=reporting_currency,
        total_value=total,
        holdings=result,
        last_updated=last_updated,
        stale=stale,
    )
