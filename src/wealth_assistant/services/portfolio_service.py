"""Portfolio service: loads data from DB and calls consolidation (T035)."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wealth_assistant.analytics.consolidation import (
    ConsolidatedPortfolio,
    HoldingInput,
    SecurityInput,
    consolidate,
)
from wealth_assistant.persistence.models import ConnectionStatus, FxRate, Investor
from wealth_assistant.persistence.repositories import (
    AccountRepository,
    ConnectionRepository,
    FxRateRepository,
    HoldingRepository,
    PriceRepository,
    SecurityRepository,
)


class PortfolioService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_portfolio(self, investor_id: uuid.UUID) -> ConsolidatedPortfolio:
        investor = await self._session.get(Investor, investor_id)
        reporting_currency = investor.reporting_currency if investor else "USD"

        hold_repo = HoldingRepository(self._session)
        sec_repo = SecurityRepository(self._session)
        price_repo = PriceRepository(self._session)
        fx_repo = FxRateRepository(self._session)
        conn_repo = ConnectionRepository(self._session)
        acct_repo = AccountRepository(self._session)

        connections = await conn_repo.list_by_investor(investor_id)
        last_updated = None
        stale = False
        for conn in connections:
            if conn.last_synced_at is not None:
                if last_updated is None or conn.last_synced_at > last_updated:
                    last_updated = conn.last_synced_at
            if conn.status in (ConnectionStatus.error, ConnectionStatus.needs_reauth):
                stale = True

        orm_holdings = await hold_repo.list_by_investor(investor_id)
        if not orm_holdings:
            return ConsolidatedPortfolio(
                reporting_currency=reporting_currency,
                total_value=Decimal("0"),
                last_updated=last_updated,
                stale=stale,
            )

        account_name_map: dict[uuid.UUID, str] = {}
        for conn in connections:
            for a in await acct_repo.list_by_connection(conn.id):
                account_name_map[a.id] = a.name or a.provider_account_id

        holding_inputs: list[HoldingInput] = []
        security_ids: set[uuid.UUID] = set()
        for h in orm_holdings:
            holding_inputs.append(HoldingInput(
                account_id=h.account_id,
                account_name=account_name_map.get(h.account_id, str(h.account_id)),
                security_id=h.security_id,
                quantity=h.quantity,
            ))
            security_ids.add(h.security_id)

        securities: dict[uuid.UUID, SecurityInput] = {}
        for sec_id in security_ids:
            sec = await sec_repo.get_by_id(sec_id)
            if sec:
                securities[sec_id] = SecurityInput(
                    id=sec.id,
                    symbol=sec.symbol,
                    name=sec.name,
                    asset_class=sec.asset_class.value,
                    sector=sec.sector,
                    currency=sec.currency,
                )

        latest_prices: dict[uuid.UUID, Decimal] = {}
        for sec_id in security_ids:
            price = await price_repo.get_latest(sec_id)
            if price:
                latest_prices[sec_id] = price.price_amount

        currencies_needed = {
            s.currency for s in securities.values() if s.currency != reporting_currency
        }
        fx_rates: dict[tuple[str, str], Decimal] = {}
        for base in currencies_needed:
            fx = await fx_repo.get(base, reporting_currency, date.today())
            if fx is None:
                stmt = (
                    select(FxRate)
                    .where(
                        FxRate.base_currency == base,
                        FxRate.quote_currency == reporting_currency,
                    )
                    .order_by(FxRate.as_of.desc())
                    .limit(1)
                )
                result = await self._session.execute(stmt)
                fx = result.scalar_one_or_none()
            if fx:
                fx_rates[(base, reporting_currency)] = fx.rate

        return consolidate(
            holdings=holding_inputs,
            securities=securities,
            latest_prices=latest_prices,
            fx_rates=fx_rates,
            reporting_currency=reporting_currency,
            last_updated=last_updated,
            stale=stale,
        )
