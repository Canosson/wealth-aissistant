"""SQLAlchemy 2.0 ORM models — all 9 entities from data-model.md (T013).

Rules:
- Monetary/quantity columns use NUMERIC (never FLOAT).
- Every investor-scoped table carries investor_id for isolation (FR-013).
- FKs use ON DELETE CASCADE to support cascading erasure (FR-018).
"""
from __future__ import annotations

import enum
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    CHAR,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wealth_assistant.persistence.db import Base


# ── Enums ─────────────────────────────────────────────────────────────────────

class ConnectionStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    needs_reauth = "needs_reauth"
    error = "error"
    unlinked = "unlinked"


class AccountType(str, enum.Enum):
    brokerage = "brokerage"
    cash = "cash"
    other = "other"


class AssetClass(str, enum.Enum):
    equity = "equity"
    etf = "etf"
    fund = "fund"
    fixed_income = "fixed_income"
    cash = "cash"
    crypto = "crypto"
    other = "other"
    unclassified = "unclassified"


# ── Entities ──────────────────────────────────────────────────────────────────

class Investor(Base):
    __tablename__ = "investors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    reporting_currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    connections: Mapped[list[LinkedAccountConnection]] = relationship(
        back_populates="investor", cascade="all, delete-orphan"
    )
    snapshots: Mapped[list[PortfolioSnapshot]] = relationship(
        back_populates="investor", cascade="all, delete-orphan"
    )
    cash_flows: Mapped[list[CashFlow]] = relationship(
        back_populates="investor", cascade="all, delete-orphan"
    )


class LinkedAccountConnection(Base):
    __tablename__ = "linked_account_connections"
    __table_args__ = (
        UniqueConstraint("investor_id", "provider", "provider_item_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    investor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_item_id: Mapped[str] = mapped_column(String(256), nullable=False)
    institution_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ConnectionStatus] = mapped_column(
        Enum(ConnectionStatus, name="connection_status"), nullable=False
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Encrypted access token — never returned to clients (FR-015)
    encrypted_access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    investor: Mapped[Investor] = relationship(back_populates="connections")
    accounts: Mapped[list[Account]] = relationship(
        back_populates="connection", cascade="all, delete-orphan"
    )


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("connection_id", "provider_account_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("linked_account_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider_account_id: Mapped[str] = mapped_column(String(256), nullable=False)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[AccountType] = mapped_column(
        Enum(AccountType, name="account_type"), nullable=False, default=AccountType.other
    )
    currency: Mapped[str | None] = mapped_column(CHAR(3), nullable=True)
    cash_balance_amount: Mapped[float | None] = mapped_column(Numeric(20, 4), nullable=True)
    cash_balance_currency: Mapped[str | None] = mapped_column(CHAR(3), nullable=True)

    connection: Mapped[LinkedAccountConnection] = relationship(back_populates="accounts")
    holdings: Mapped[list[Holding]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )


class Security(Base):
    __tablename__ = "securities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    symbol: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    asset_class: Mapped[AssetClass] = mapped_column(
        Enum(AssetClass, name="asset_class_enum"),
        nullable=False,
        default=AssetClass.unclassified,
    )
    sector: Mapped[str | None] = mapped_column(String(128), nullable=True)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)

    holdings: Mapped[list[Holding]] = relationship(back_populates="security")
    prices: Mapped[list[Price]] = relationship(
        back_populates="security", cascade="all, delete-orphan"
    )
    snapshot_holdings: Mapped[list[SnapshotHolding]] = relationship(
        back_populates="security"
    )


class Holding(Base):
    __tablename__ = "holdings"
    __table_args__ = (UniqueConstraint("account_id", "security_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("securities.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    cost_basis_amount: Mapped[float | None] = mapped_column(Numeric(20, 4), nullable=True)
    cost_basis_currency: Mapped[str | None] = mapped_column(CHAR(3), nullable=True)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    account: Mapped[Account] = relationship(back_populates="holdings")
    security: Mapped[Security] = relationship(back_populates="holdings")


class Price(Base):
    __tablename__ = "prices"
    __table_args__ = (UniqueConstraint("security_id", "as_of"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("securities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    price_amount: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    price_currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)

    security: Mapped[Security] = relationship(back_populates="prices")


class FxRate(Base):
    __tablename__ = "fx_rates"
    __table_args__ = (UniqueConstraint("base_currency", "quote_currency", "as_of"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    base_currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    quote_currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    rate: Mapped[float] = mapped_column(Numeric(20, 10), nullable=False)
    as_of: Mapped[date] = mapped_column(Date, nullable=False, index=True)


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"
    __table_args__ = (UniqueConstraint("investor_id", "as_of"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    investor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    total_value_amount: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    total_value_currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    net_external_flow_amount: Mapped[float] = mapped_column(
        Numeric(20, 4), nullable=False, default=0
    )

    investor: Mapped[Investor] = relationship(back_populates="snapshots")
    snapshot_holdings: Mapped[list[SnapshotHolding]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan"
    )


class CashFlow(Base):
    """Signed ledger of external cash flows in the investor's reporting currency.

    Positive amount = deposit, negative = withdrawal. The snapshot service sums
    flows between snapshots to populate net_external_flow_amount, so period
    returns correctly exclude new capital from reported gains.
    """
    __tablename__ = "cash_flows"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    investor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    investor: Mapped[Investor] = relationship(back_populates="cash_flows")


class SnapshotHolding(Base):
    __tablename__ = "snapshot_holdings"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("portfolio_snapshots.id", ondelete="CASCADE"),
        primary_key=True,
    )
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("securities.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    quantity: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    price_amount: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    price_currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    fx_rate: Mapped[float] = mapped_column(Numeric(20, 10), nullable=False, default=1)
    value_amount: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    value_currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)

    snapshot: Mapped[PortfolioSnapshot] = relationship(back_populates="snapshot_holdings")
    security: Mapped[Security] = relationship(back_populates="snapshot_holdings")
