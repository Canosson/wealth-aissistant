"""P0: SnapshotService records REAL prices and FX rates (no placeholders).

Snapshots are the reproducibility record (research R6): each SnapshotHolding
must freeze the actual price and FX rate used for valuation — never
price_amount=0 / fx_rate=1 placeholders. Also covers idempotency, the empty-
portfolio case, and the scheduler-disabled-by-default guard.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
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
    Price,
    Security,
    SnapshotHolding,
)
from wealth_assistant.services.snapshot_service import SnapshotService


@pytest_asyncio.fixture
async def seeded_investor(db_session: AsyncSession) -> uuid.UUID:
    """Investor with one USD holding (10 × 150.00) and one EUR holding (4 × 200.00 @ 1.10)."""
    investor = Investor(
        id=uuid.uuid4(),
        email=f"snap-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="x",
        reporting_currency="USD",
    )
    conn = LinkedAccountConnection(
        id=uuid.uuid4(),
        investor_id=investor.id,
        provider="fake",
        provider_item_id="item-1",
        institution_name="Fake Bank",
        status=ConnectionStatus.active,
        last_synced_at=datetime.now(UTC),
    )
    account = Account(
        id=uuid.uuid4(),
        connection_id=conn.id,
        provider_account_id="acct-1",
        name="Brokerage",
        type=AccountType.brokerage,
        currency="USD",
    )
    sec_usd = Security(
        id=uuid.uuid4(), symbol="AAPL", name="Apple Inc.",
        asset_class=AssetClass.equity, sector="Technology", currency="USD",
    )
    sec_eur = Security(
        id=uuid.uuid4(), symbol="SAP", name="SAP SE",
        asset_class=AssetClass.equity, sector="Technology", currency="EUR",
    )
    today = date.today()
    rows = [
        investor, conn, account, sec_usd, sec_eur,
        Holding(id=uuid.uuid4(), account_id=account.id, security_id=sec_usd.id,
                quantity=Decimal("10"), as_of=datetime.now(UTC)),
        Holding(id=uuid.uuid4(), account_id=account.id, security_id=sec_eur.id,
                quantity=Decimal("4"), as_of=datetime.now(UTC)),
        Price(id=uuid.uuid4(), security_id=sec_usd.id,
              price_amount=Decimal("150.00"), price_currency="USD", as_of=today),
        Price(id=uuid.uuid4(), security_id=sec_eur.id,
              price_amount=Decimal("200.00"), price_currency="EUR", as_of=today),
        FxRate(id=uuid.uuid4(), base_currency="EUR", quote_currency="USD",
               rate=Decimal("1.10"), as_of=today),
    ]
    db_session.add_all(rows)
    await db_session.commit()
    return investor.id


async def _snapshot_holdings(db_session: AsyncSession, snapshot_id) -> list[SnapshotHolding]:
    result = await db_session.execute(
        select(SnapshotHolding).where(SnapshotHolding.snapshot_id == snapshot_id)
    )
    return list(result.scalars())


class TestSnapshotRecordsRealInputs:
    async def test_total_value_is_correct(self, db_session: AsyncSession, seeded_investor):
        snap = await SnapshotService(db_session).snapshot_investor(seeded_investor)
        await db_session.commit()
        assert snap is not None
        # 10 × 150 + 4 × 200 × 1.10 = 1500 + 880 = 2380
        assert Decimal(str(snap.total_value_amount)) == Decimal("2380")
        assert snap.total_value_currency == "USD"

    async def test_records_real_price_not_zero(self, db_session: AsyncSession, seeded_investor):
        snap = await SnapshotService(db_session).snapshot_investor(seeded_investor)
        await db_session.commit()
        holdings = await _snapshot_holdings(db_session, snap.id)
        assert len(holdings) == 2
        prices = sorted(Decimal(str(h.price_amount)) for h in holdings)
        assert prices == [Decimal("150"), Decimal("200")], (
            "SnapshotHolding must freeze the actual prices used, not placeholders"
        )
        assert all(Decimal(str(h.price_amount)) > 0 for h in holdings)

    async def test_records_native_price_currency(self, db_session: AsyncSession, seeded_investor):
        snap = await SnapshotService(db_session).snapshot_investor(seeded_investor)
        await db_session.commit()
        holdings = await _snapshot_holdings(db_session, snap.id)
        currencies = {h.price_currency for h in holdings}
        assert currencies == {"USD", "EUR"}, (
            "price_currency must be the security's native quote currency"
        )

    async def test_records_real_fx_rate(self, db_session: AsyncSession, seeded_investor):
        snap = await SnapshotService(db_session).snapshot_investor(seeded_investor)
        await db_session.commit()
        holdings = await _snapshot_holdings(db_session, snap.id)
        by_ccy = {h.price_currency: h for h in holdings}
        assert Decimal(str(by_ccy["USD"].fx_rate)) == Decimal("1")
        assert Decimal(str(by_ccy["EUR"].fx_rate)) == Decimal("1.10"), (
            "fx_rate must be the recorded conversion rate, not a placeholder 1"
        )

    async def test_value_reproducible_from_frozen_inputs(
        self, db_session: AsyncSession, seeded_investor
    ):
        """Principle VI: value_amount == quantity × price × fx for every row."""
        snap = await SnapshotService(db_session).snapshot_investor(seeded_investor)
        await db_session.commit()
        for h in await _snapshot_holdings(db_session, snap.id):
            recomputed = (
                Decimal(str(h.quantity))
                * Decimal(str(h.price_amount))
                * Decimal(str(h.fx_rate))
            )
            assert Decimal(str(h.value_amount)) == recomputed


class TestSnapshotLifecycle:
    async def test_idempotent_per_day(self, db_session: AsyncSession, seeded_investor):
        svc = SnapshotService(db_session)
        first = await svc.snapshot_investor(seeded_investor)
        await db_session.commit()
        second = await svc.snapshot_investor(seeded_investor)
        assert second is not None
        assert second.id == first.id

    async def test_empty_portfolio_returns_none(self, db_session: AsyncSession):
        investor = Investor(
            id=uuid.uuid4(),
            email=f"empty-{uuid.uuid4().hex[:8]}@example.com",
            password_hash="x",
            reporting_currency="USD",
        )
        db_session.add(investor)
        await db_session.commit()
        snap = await SnapshotService(db_session).snapshot_investor(investor.id)
        assert snap is None


class TestSchedulerGuard:
    def test_snapshot_job_disabled_by_default(self):
        from wealth_assistant.config import Settings
        assert Settings().snapshot_job_enabled is False

    def test_register_jobs_skips_when_disabled(self, monkeypatch):
        from wealth_assistant.scheduler import app as sched_app

        monkeypatch.setattr(sched_app, "_scheduler", None)
        sched_app.register_jobs()
        assert sched_app.get_scheduler().get_job("weekly_snapshot") is None, (
            "weekly_snapshot must NOT be registered while snapshot_job_enabled=False"
        )
