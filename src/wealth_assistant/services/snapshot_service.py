"""T043: Snapshot service — portfolio → PortfolioSnapshot + SnapshotHolding rows."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from wealth_assistant.persistence.models import PortfolioSnapshot, SnapshotHolding
from wealth_assistant.persistence.repositories import (
    CashFlowRepository,
    InvestorRepository,
    SnapshotRepository,
)
from wealth_assistant.services.portfolio_service import PortfolioService


class SnapshotService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def snapshot_investor(self, investor_id: uuid.UUID) -> PortfolioSnapshot | None:
        """Value current portfolio and persist a daily snapshot. Idempotent per day."""
        today = date.today()
        snap_repo = SnapshotRepository(self._session)

        existing = await snap_repo.get_by_date(investor_id, today)
        if existing:
            return existing

        portfolio = await PortfolioService(self._session).get_portfolio(investor_id)
        if portfolio.total_value == Decimal("0") and not portfolio.holdings:
            return None

        prev_snap = await snap_repo.get_latest_before(investor_id, before_date=today)
        if prev_snap is not None:
            net_flow = await CashFlowRepository(self._session).net_between(
                investor_id,
                from_date_exclusive=prev_snap.as_of,
                to_date_inclusive=today,
            )
        else:
            net_flow = Decimal("0")

        snapshot = PortfolioSnapshot(
            id=uuid.uuid4(),
            investor_id=investor_id,
            as_of=today,
            total_value_amount=portfolio.total_value,
            total_value_currency=portfolio.reporting_currency,
            net_external_flow_amount=Decimal(str(net_flow)),
        )
        self._session.add(snapshot)
        await self._session.flush()

        for h in portfolio.holdings:
            if not h.price_available or h.value_amount is None or h.price_amount is None:
                continue
            # Freeze the actual valuation inputs (price, native currency, FX rate)
            # so the snapshot is reproducible (Principle VI, research R6).
            sh = SnapshotHolding(
                snapshot_id=snapshot.id,
                security_id=h.security_id,
                quantity=h.quantity,
                price_amount=h.price_amount,
                price_currency=h.price_currency or portfolio.reporting_currency,
                fx_rate=h.fx_rate,
                value_amount=h.value_amount,
                value_currency=portfolio.reporting_currency,
            )
            self._session.add(sh)

        return snapshot

    async def snapshot_all_investors(self) -> int:
        """Take snapshots for every investor. Returns count of snapshots created."""
        inv_repo = InvestorRepository(self._session)
        investors = await inv_repo.list_all()
        count = 0
        for investor in investors:
            snap = await self.snapshot_investor(investor.id)
            if snap:
                count += 1
        return count
