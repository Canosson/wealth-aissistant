"""Repositories: typed data access for each domain entity (T015).

All reads are investor-scoped (FR-013). Repositories accept an AsyncSession
so the calling service controls the transaction boundary via unit_of_work().
"""
from __future__ import annotations

import uuid
from datetime import date
from typing import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from wealth_assistant.persistence.models import (
    Account,
    CashFlow,
    FxRate,
    Holding,
    Investor,
    LinkedAccountConnection,
    PortfolioSnapshot,
    Price,
    Security,
)


# ── Investor ──────────────────────────────────────────────────────────────────

class InvestorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, investor: Investor) -> None:
        self._s.add(investor)

    async def get_by_id(self, investor_id: uuid.UUID) -> Investor | None:
        return await self._s.get(Investor, investor_id)

    async def get_by_email(self, email: str) -> Investor | None:
        result = await self._s.execute(select(Investor).where(Investor.email == email))
        return result.scalar_one_or_none()

    async def delete(self, investor: Investor) -> None:
        await self._s.delete(investor)

    async def list_all(self) -> list[Investor]:
        result = await self._s.execute(select(Investor))
        return list(result.scalars().all())


# ── LinkedAccountConnection ───────────────────────────────────────────────────

class ConnectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, connection: LinkedAccountConnection) -> None:
        self._s.add(connection)

    async def get_by_id(
        self, connection_id: uuid.UUID, investor_id: uuid.UUID
    ) -> LinkedAccountConnection | None:
        stmt = select(LinkedAccountConnection).where(
            LinkedAccountConnection.id == connection_id,
            LinkedAccountConnection.investor_id == investor_id,
        )
        result = await self._s.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_investor(
        self, investor_id: uuid.UUID
    ) -> Sequence[LinkedAccountConnection]:
        stmt = select(LinkedAccountConnection).where(
            LinkedAccountConnection.investor_id == investor_id
        )
        result = await self._s.execute(stmt)
        return result.scalars().all()

    async def delete(self, connection: LinkedAccountConnection) -> None:
        await self._s.delete(connection)


# ── Account ───────────────────────────────────────────────────────────────────

class AccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, account: Account) -> None:
        self._s.add(account)

    async def list_by_connection(self, connection_id: uuid.UUID) -> Sequence[Account]:
        stmt = select(Account).where(Account.connection_id == connection_id)
        result = await self._s.execute(stmt)
        return result.scalars().all()

    async def get_by_provider_account_id(
        self, connection_id: uuid.UUID, provider_account_id: str
    ) -> Account | None:
        stmt = select(Account).where(
            Account.connection_id == connection_id,
            Account.provider_account_id == provider_account_id,
        )
        result = await self._s.execute(stmt)
        return result.scalar_one_or_none()


# ── Security ──────────────────────────────────────────────────────────────────

class SecurityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, security: Security) -> None:
        self._s.add(security)

    async def get_by_symbol_and_currency(
        self, symbol: str, currency: str
    ) -> Security | None:
        stmt = select(Security).where(
            Security.symbol == symbol,
            Security.currency == currency,
        )
        result = await self._s.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, security_id: uuid.UUID) -> Security | None:
        return await self._s.get(Security, security_id)


# ── Holding ───────────────────────────────────────────────────────────────────

class HoldingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, holding: Holding) -> None:
        self._s.add(holding)

    async def list_by_investor(self, investor_id: uuid.UUID) -> Sequence[Holding]:
        """All holdings across all accounts owned by an investor."""
        stmt = (
            select(Holding)
            .join(Account, Holding.account_id == Account.id)
            .join(
                LinkedAccountConnection,
                Account.connection_id == LinkedAccountConnection.id,
            )
            .where(LinkedAccountConnection.investor_id == investor_id)
        )
        result = await self._s.execute(stmt)
        return result.scalars().all()

    async def delete_by_connection(self, connection_id: uuid.UUID) -> None:
        stmt = delete(Holding).where(
            Holding.account_id.in_(
                select(Account.id).where(Account.connection_id == connection_id)
            )
        )
        await self._s.execute(stmt)


# ── Price ─────────────────────────────────────────────────────────────────────

class PriceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, price: Price) -> None:
        self._s.add(price)

    async def get_latest(self, security_id: uuid.UUID) -> Price | None:
        stmt = (
            select(Price)
            .where(Price.security_id == security_id)
            .order_by(Price.as_of.desc())
            .limit(1)
        )
        result = await self._s.execute(stmt)
        return result.scalar_one_or_none()


# ── FxRate ────────────────────────────────────────────────────────────────────

class FxRateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, fx_rate: FxRate) -> None:
        self._s.add(fx_rate)

    async def get(self, base: str, quote: str, as_of: date) -> FxRate | None:
        stmt = select(FxRate).where(
            FxRate.base_currency == base,
            FxRate.quote_currency == quote,
            FxRate.as_of == as_of,
        )
        result = await self._s.execute(stmt)
        return result.scalar_one_or_none()


# ── PortfolioSnapshot ─────────────────────────────────────────────────────────

class SnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, snapshot: PortfolioSnapshot) -> None:
        self._s.add(snapshot)

    async def list_by_investor(
        self, investor_id: uuid.UUID
    ) -> Sequence[PortfolioSnapshot]:
        stmt = (
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.investor_id == investor_id)
            .order_by(PortfolioSnapshot.as_of.asc())
        )
        result = await self._s.execute(stmt)
        return result.scalars().all()

    async def get_by_date(
        self, investor_id: uuid.UUID, as_of: date
    ) -> PortfolioSnapshot | None:
        stmt = select(PortfolioSnapshot).where(
            PortfolioSnapshot.investor_id == investor_id,
            PortfolioSnapshot.as_of == as_of,
        )
        result = await self._s.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_before(
        self, investor_id: uuid.UUID, before_date: date
    ) -> PortfolioSnapshot | None:
        """Return the most recent snapshot with as_of strictly before before_date."""
        stmt = (
            select(PortfolioSnapshot)
            .where(
                PortfolioSnapshot.investor_id == investor_id,
                PortfolioSnapshot.as_of < before_date,
            )
            .order_by(PortfolioSnapshot.as_of.desc())
            .limit(1)
        )
        result = await self._s.execute(stmt)
        return result.scalar_one_or_none()


# ── CashFlow ──────────────────────────────────────────────────────────────────

class CashFlowRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(
        self,
        investor_id: uuid.UUID,
        occurred_on: date,
        amount: float,
        currency: str,
        description: str | None = None,
    ) -> CashFlow:
        flow = CashFlow(
            id=uuid.uuid4(),
            investor_id=investor_id,
            occurred_on=occurred_on,
            amount=amount,
            currency=currency,
            description=description,
        )
        self._s.add(flow)
        return flow

    async def net_between(
        self,
        investor_id: uuid.UUID,
        from_date_exclusive: date,
        to_date_inclusive: date,
    ) -> float:
        """Sum of signed amounts for flows in (from_date_exclusive, to_date_inclusive]."""
        stmt = select(func.coalesce(func.sum(CashFlow.amount), 0)).where(
            CashFlow.investor_id == investor_id,
            CashFlow.occurred_on > from_date_exclusive,
            CashFlow.occurred_on <= to_date_inclusive,
        )
        result = await self._s.execute(stmt)
        return result.scalar_one()
