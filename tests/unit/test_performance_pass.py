"""T055: Performance pass — consolidated portfolio of ~500 holdings renders in < 2 s.

Pure unit test against the consolidation function; no DB or network required.
Acceptance criterion: SC-007.
"""
from __future__ import annotations

import time
import uuid
from decimal import Decimal

import pytest

from wealth_assistant.analytics.consolidation import (
    ConsolidatedPortfolio,
    HoldingInput,
    SecurityInput,
    consolidate,
)

_PERF_LIMIT_SECONDS = 2.0
_N_HOLDINGS = 500


def _build_inputs(n: int) -> tuple[
    list[HoldingInput],
    dict[uuid.UUID, SecurityInput],
    dict[uuid.UUID, Decimal],
    dict[tuple[str, str], Decimal],
]:
    securities: dict[uuid.UUID, SecurityInput] = {}
    holdings: list[HoldingInput] = []
    prices: dict[uuid.UUID, Decimal] = {}
    account_id = uuid.uuid4()

    for i in range(n):
        sec_id = uuid.uuid4()
        currency = "USD" if i % 5 != 0 else "EUR"
        asset_class = ["equity", "etf", "fund", "fixed_income", "cash"][i % 5]
        sector = ["Technology", "Finance", "Healthcare", "Energy", None][i % 5]

        securities[sec_id] = SecurityInput(
            id=sec_id,
            symbol=f"SEC{i:04d}",
            name=f"Security {i}",
            asset_class=asset_class,
            sector=sector,
            currency=currency,
        )
        holdings.append(
            HoldingInput(
                account_id=account_id,
                account_name="Benchmark Account",
                security_id=sec_id,
                quantity=Decimal("10.5"),
            )
        )
        prices[sec_id] = Decimal("100.00")

    fx_rates: dict[tuple[str, str], Decimal] = {("EUR", "USD"): Decimal("1.10")}
    return holdings, securities, prices, fx_rates


@pytest.mark.parametrize("n", [_N_HOLDINGS])
def test_consolidation_under_2_seconds(n: int) -> None:
    holdings, securities, prices, fx_rates = _build_inputs(n)

    start = time.perf_counter()
    result: ConsolidatedPortfolio = consolidate(
        holdings=holdings,
        securities=securities,
        latest_prices=prices,
        fx_rates=fx_rates,
        reporting_currency="USD",
    )
    elapsed = time.perf_counter() - start

    assert len(result.holdings) == n, f"Expected {n} holdings, got {len(result.holdings)}"
    assert result.total_value > Decimal("0"), "Total value must be positive"
    assert elapsed < _PERF_LIMIT_SECONDS, (
        f"Consolidation of {n} holdings took {elapsed:.3f}s, limit is {_PERF_LIMIT_SECONDS}s"
    )


def test_consolidation_dedup_across_accounts_under_2_seconds() -> None:
    """500 holdings split across 2 accounts (250 unique securities, each in both accounts)."""
    securities: dict[uuid.UUID, SecurityInput] = {}
    holdings: list[HoldingInput] = []
    prices: dict[uuid.UUID, Decimal] = {}

    account_a = uuid.uuid4()
    account_b = uuid.uuid4()
    n_securities = 250

    for i in range(n_securities):
        sec_id = uuid.uuid4()
        securities[sec_id] = SecurityInput(
            id=sec_id, symbol=f"DUP{i:03d}", name=f"Dup {i}",
            asset_class="equity", sector="Technology", currency="USD",
        )
        prices[sec_id] = Decimal("50.00")
        for account_id, name in [(account_a, "Account A"), (account_b, "Account B")]:
            holdings.append(HoldingInput(
                account_id=account_id, account_name=name,
                security_id=sec_id, quantity=Decimal("5"),
            ))

    start = time.perf_counter()
    result = consolidate(
        holdings=holdings,
        securities=securities,
        latest_prices=prices,
        fx_rates={},
        reporting_currency="USD",
    )
    elapsed = time.perf_counter() - start

    assert len(result.holdings) == n_securities
    assert all(len(h.accounts) == 2 for h in result.holdings)
    assert elapsed < _PERF_LIMIT_SECONDS, (
        f"Dedup consolidation took {elapsed:.3f}s, limit is {_PERF_LIMIT_SECONDS}s"
    )
