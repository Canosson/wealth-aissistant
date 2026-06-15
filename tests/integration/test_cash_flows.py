"""P0: Net external flows ledger — correctness tests.

A deposit between two snapshots must appear as net_external_flow_amount, not
as an investment gain. Covers the repository, snapshot integration, and the
performance correction.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wealth_assistant.persistence.models import (
    Account,
    AccountType,
    AssetClass,
    ConnectionStatus,
    FxRate,
    Holding,
    Investor,
    LinkedAccountConnection,
    PortfolioSnapshot,
    Price,
    Security,
)
from wealth_assistant.persistence.repositories import CashFlowRepository, SnapshotRepository
from wealth_assistant.services.snapshot_service import SnapshotService


# ── Shared fixtures ───────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def investor(db_session: AsyncSession) -> Investor:
    inv = Investor(
        id=uuid.uuid4(),
        email=f"flows-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="x",
        reporting_currency="USD",
    )
    db_session.add(inv)
    await db_session.commit()
    return inv


@pytest_asyncio.fixture
async def other_investor(db_session: AsyncSession) -> Investor:
    inv = Investor(
        id=uuid.uuid4(),
        email=f"other-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="x",
        reporting_currency="USD",
    )
    db_session.add(inv)
    await db_session.commit()
    return inv


@pytest_asyncio.fixture
async def investor_with_holding(db_session: AsyncSession) -> tuple[uuid.UUID, date]:
    """Investor with one $100 holding and a price, ready for snapshotting."""
    today = date.today()
    inv = Investor(
        id=uuid.uuid4(),
        email=f"snap-flows-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="x",
        reporting_currency="USD",
    )
    conn = LinkedAccountConnection(
        id=uuid.uuid4(),
        investor_id=inv.id,
        provider="fake",
        provider_item_id="item-flows",
        institution_name="Fake Bank",
        status=ConnectionStatus.active,
        last_synced_at=datetime.now(UTC),
    )
    account = Account(
        id=uuid.uuid4(),
        connection_id=conn.id,
        provider_account_id="acct-flows",
        name="Brokerage",
        type=AccountType.brokerage,
        currency="USD",
    )
    sec = Security(
        id=uuid.uuid4(), symbol="TSLA", name="Tesla Inc.",
        asset_class=AssetClass.equity, sector="Tech", currency="USD",
    )
    rows = [
        inv, conn, account, sec,
        Holding(id=uuid.uuid4(), account_id=account.id, security_id=sec.id,
                quantity=Decimal("1"), as_of=datetime.now(UTC)),
        Price(id=uuid.uuid4(), security_id=sec.id,
              price_amount=Decimal("100.00"), price_currency="USD", as_of=today),
    ]
    db_session.add_all(rows)
    await db_session.commit()
    return inv.id, today


# ── CashFlowRepository ────────────────────────────────────────────────────────


class TestCashFlowRepository:
    async def test_net_between_is_zero_with_no_flows(
        self, db_session: AsyncSession, investor: Investor
    ) -> None:
        repo = CashFlowRepository(db_session)
        net = await repo.net_between(
            investor.id,
            from_date_exclusive=date(2026, 1, 1),
            to_date_inclusive=date(2026, 6, 13),
        )
        assert net == Decimal("0")

    async def test_net_between_sums_flows_in_window(
        self, db_session: AsyncSession, investor: Investor
    ) -> None:
        repo = CashFlowRepository(db_session)
        await repo.add(investor.id, occurred_on=date(2026, 1, 5),
                       amount=Decimal("500.00"), currency="USD")
        await repo.add(investor.id, occurred_on=date(2026, 1, 10),
                       amount=Decimal("-200.00"), currency="USD")
        await db_session.commit()

        net = await repo.net_between(
            investor.id,
            from_date_exclusive=date(2026, 1, 1),
            to_date_inclusive=date(2026, 1, 31),
        )
        assert net == Decimal("300.00")

    async def test_net_between_excludes_flows_outside_window(
        self, db_session: AsyncSession, investor: Investor
    ) -> None:
        repo = CashFlowRepository(db_session)
        await repo.add(investor.id, occurred_on=date(2026, 1, 1),   # on from_date → excluded
                       amount=Decimal("1000.00"), currency="USD")
        await repo.add(investor.id, occurred_on=date(2026, 1, 5),   # inside → included
                       amount=Decimal("200.00"), currency="USD")
        await repo.add(investor.id, occurred_on=date(2026, 1, 20),  # after to_date → excluded
                       amount=Decimal("999.00"), currency="USD")
        await db_session.commit()

        net = await repo.net_between(
            investor.id,
            from_date_exclusive=date(2026, 1, 1),
            to_date_inclusive=date(2026, 1, 10),
        )
        assert net == Decimal("200.00")

    async def test_net_between_scoped_to_investor(
        self,
        db_session: AsyncSession,
        investor: Investor,
        other_investor: Investor,
    ) -> None:
        repo = CashFlowRepository(db_session)
        await repo.add(investor.id, occurred_on=date(2026, 1, 5),
                       amount=Decimal("100.00"), currency="USD")
        await repo.add(other_investor.id, occurred_on=date(2026, 1, 5),
                       amount=Decimal("99999.00"), currency="USD")
        await db_session.commit()

        net = await repo.net_between(
            investor.id,
            from_date_exclusive=date(2026, 1, 1),
            to_date_inclusive=date(2026, 1, 31),
        )
        assert net == Decimal("100.00")

    async def test_cascade_delete_removes_flows(
        self, db_session: AsyncSession, investor: Investor
    ) -> None:
        from wealth_assistant.persistence.models import CashFlow

        repo = CashFlowRepository(db_session)
        await repo.add(investor.id, occurred_on=date(2026, 1, 5),
                       amount=Decimal("500.00"), currency="USD")
        await db_session.commit()

        await db_session.delete(investor)
        await db_session.commit()

        result = await db_session.execute(
            select(CashFlow).where(CashFlow.investor_id == investor.id)
        )
        assert result.scalars().all() == []


# ── SnapshotRepository.get_latest_before ─────────────────────────────────────


class TestSnapshotRepositoryLatestBefore:
    async def test_returns_none_when_no_prior_snapshot(
        self, db_session: AsyncSession, investor: Investor
    ) -> None:
        repo = SnapshotRepository(db_session)
        result = await repo.get_latest_before(investor.id, before_date=date.today())
        assert result is None

    async def test_returns_most_recent_snapshot_before_date(
        self, db_session: AsyncSession, investor: Investor
    ) -> None:
        today = date.today()
        older = PortfolioSnapshot(
            id=uuid.uuid4(), investor_id=investor.id,
            as_of=today - timedelta(days=14),
            total_value_amount=Decimal("1000"), total_value_currency="USD",
            net_external_flow_amount=Decimal("0"),
        )
        newer = PortfolioSnapshot(
            id=uuid.uuid4(), investor_id=investor.id,
            as_of=today - timedelta(days=7),
            total_value_amount=Decimal("1100"), total_value_currency="USD",
            net_external_flow_amount=Decimal("0"),
        )
        db_session.add_all([older, newer])
        await db_session.commit()

        repo = SnapshotRepository(db_session)
        result = await repo.get_latest_before(investor.id, before_date=today)
        assert result is not None
        assert result.id == newer.id

    async def test_excludes_snapshot_on_exact_date(
        self, db_session: AsyncSession, investor: Investor
    ) -> None:
        today = date.today()
        snap = PortfolioSnapshot(
            id=uuid.uuid4(), investor_id=investor.id,
            as_of=today,
            total_value_amount=Decimal("500"), total_value_currency="USD",
            net_external_flow_amount=Decimal("0"),
        )
        db_session.add(snap)
        await db_session.commit()

        repo = SnapshotRepository(db_session)
        result = await repo.get_latest_before(investor.id, before_date=today)
        assert result is None


# ── SnapshotService: flows integration ───────────────────────────────────────


class TestSnapshotRecordsNetFlows:
    async def test_no_prior_snapshot_flow_is_zero(
        self, db_session: AsyncSession, investor_with_holding: tuple
    ) -> None:
        """First-ever snapshot: no window to look back through, net flow = 0."""
        investor_id, _ = investor_with_holding
        snap = await SnapshotService(db_session).snapshot_investor(investor_id)
        await db_session.commit()
        assert snap is not None
        assert Decimal(str(snap.net_external_flow_amount)) == Decimal("0")

    async def test_deposit_between_snapshots_recorded_as_net_flow(
        self, db_session: AsyncSession, investor_with_holding: tuple
    ) -> None:
        """Deposit of $500 after previous snapshot → net_external_flow_amount = 500."""
        investor_id, today = investor_with_holding

        prev_date = today - timedelta(days=7)
        db_session.add(PortfolioSnapshot(
            id=uuid.uuid4(), investor_id=investor_id,
            as_of=prev_date,
            total_value_amount=Decimal("100"), total_value_currency="USD",
            net_external_flow_amount=Decimal("0"),
        ))
        flow_repo = CashFlowRepository(db_session)
        await flow_repo.add(investor_id, occurred_on=today - timedelta(days=3),
                            amount=Decimal("500.00"), currency="USD")
        await db_session.commit()

        snap = await SnapshotService(db_session).snapshot_investor(investor_id)
        await db_session.commit()
        assert snap is not None
        assert Decimal(str(snap.net_external_flow_amount)) == Decimal("500.00")

    async def test_withdrawal_between_snapshots_is_negative_flow(
        self, db_session: AsyncSession, investor_with_holding: tuple
    ) -> None:
        investor_id, today = investor_with_holding

        prev_date = today - timedelta(days=7)
        db_session.add(PortfolioSnapshot(
            id=uuid.uuid4(), investor_id=investor_id,
            as_of=prev_date,
            total_value_amount=Decimal("1000"), total_value_currency="USD",
            net_external_flow_amount=Decimal("0"),
        ))
        flow_repo = CashFlowRepository(db_session)
        await flow_repo.add(investor_id, occurred_on=today - timedelta(days=2),
                            amount=Decimal("-300.00"), currency="USD")
        await db_session.commit()

        snap = await SnapshotService(db_session).snapshot_investor(investor_id)
        await db_session.commit()
        assert snap is not None
        assert Decimal(str(snap.net_external_flow_amount)) == Decimal("-300.00")

    async def test_flows_before_previous_snapshot_excluded(
        self, db_session: AsyncSession, investor_with_holding: tuple
    ) -> None:
        """A flow recorded before the prior snapshot must not be double-counted."""
        investor_id, today = investor_with_holding

        prev_date = today - timedelta(days=7)
        db_session.add(PortfolioSnapshot(
            id=uuid.uuid4(), investor_id=investor_id,
            as_of=prev_date,
            total_value_amount=Decimal("500"), total_value_currency="USD",
            net_external_flow_amount=Decimal("0"),
        ))
        flow_repo = CashFlowRepository(db_session)
        await flow_repo.add(investor_id, occurred_on=prev_date - timedelta(days=1),
                            amount=Decimal("9999.00"), currency="USD")
        await flow_repo.add(investor_id, occurred_on=today - timedelta(days=3),
                            amount=Decimal("100.00"), currency="USD")
        await db_session.commit()

        snap = await SnapshotService(db_session).snapshot_investor(investor_id)
        await db_session.commit()
        assert snap is not None
        assert Decimal(str(snap.net_external_flow_amount)) == Decimal("100.00")

    async def test_multiple_flows_summed(
        self, db_session: AsyncSession, investor_with_holding: tuple
    ) -> None:
        investor_id, today = investor_with_holding

        prev_date = today - timedelta(days=14)
        db_session.add(PortfolioSnapshot(
            id=uuid.uuid4(), investor_id=investor_id,
            as_of=prev_date,
            total_value_amount=Decimal("1000"), total_value_currency="USD",
            net_external_flow_amount=Decimal("0"),
        ))
        flow_repo = CashFlowRepository(db_session)
        await flow_repo.add(investor_id, occurred_on=today - timedelta(days=10),
                            amount=Decimal("200.00"), currency="USD")
        await flow_repo.add(investor_id, occurred_on=today - timedelta(days=5),
                            amount=Decimal("300.00"), currency="USD")
        await flow_repo.add(investor_id, occurred_on=today - timedelta(days=2),
                            amount=Decimal("-50.00"), currency="USD")
        await db_session.commit()

        snap = await SnapshotService(db_session).snapshot_investor(investor_id)
        await db_session.commit()
        assert snap is not None
        assert Decimal(str(snap.net_external_flow_amount)) == Decimal("450.00")
