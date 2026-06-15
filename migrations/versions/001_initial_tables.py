"""Initial tables for portfolio analytics.

Revision ID: 001
Revises:
Create Date: 2026-06-12

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Custom types ─────────────────────────────────────────────────────────
    connection_status = postgresql.ENUM(
        "pending", "active", "needs_reauth", "error", "unlinked",
        name="connection_status",
    )
    account_type = postgresql.ENUM(
        "brokerage", "cash", "other",
        name="account_type",
    )
    asset_class_enum = postgresql.ENUM(
        "equity", "etf", "fund", "fixed_income", "cash", "crypto", "other", "unclassified",
        name="asset_class_enum",
    )
    connection_status.create(op.get_bind())
    account_type.create(op.get_bind())
    asset_class_enum.create(op.get_bind())

    # ── investors ─────────────────────────────────────────────────────────────
    op.create_table(
        "investors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), unique=True, nullable=False),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("reporting_currency", sa.CHAR(3), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ── linked_account_connections ────────────────────────────────────────────
    op.create_table(
        "linked_account_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "investor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("investors.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("provider_item_id", sa.String(256), nullable=False),
        sa.Column("institution_name", sa.Text, nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(name="connection_status", create_type=False),
            nullable=False,
        ),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("encrypted_access_token", sa.Text, nullable=True),
        sa.Column("error_detail", sa.Text, nullable=True),
        sa.UniqueConstraint("investor_id", "provider", "provider_item_id"),
    )

    # ── accounts ──────────────────────────────────────────────────────────────
    op.create_table(
        "accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("linked_account_connections.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("provider_account_id", sa.String(256), nullable=False),
        sa.Column("name", sa.Text, nullable=True),
        sa.Column(
            "type",
            postgresql.ENUM(name="account_type", create_type=False),
            nullable=False,
        ),
        sa.Column("currency", sa.CHAR(3), nullable=True),
        sa.Column("cash_balance_amount", sa.Numeric(20, 4), nullable=True),
        sa.Column("cash_balance_currency", sa.CHAR(3), nullable=True),
        sa.UniqueConstraint("connection_id", "provider_account_id"),
    )

    # ── securities ────────────────────────────────────────────────────────────
    op.create_table(
        "securities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("symbol", sa.String(32), nullable=True, index=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column(
            "asset_class",
            postgresql.ENUM(name="asset_class_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("sector", sa.String(128), nullable=True),
        sa.Column("currency", sa.CHAR(3), nullable=False),
    )

    # ── holdings ──────────────────────────────────────────────────────────────
    op.create_table(
        "holdings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "security_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("securities.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("quantity", sa.Numeric(20, 8), nullable=False),
        sa.Column("cost_basis_amount", sa.Numeric(20, 4), nullable=True),
        sa.Column("cost_basis_currency", sa.CHAR(3), nullable=True),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("account_id", "security_id"),
    )

    # ── prices ────────────────────────────────────────────────────────────────
    op.create_table(
        "prices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "security_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("securities.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("price_amount", sa.Numeric(20, 4), nullable=False),
        sa.Column("price_currency", sa.CHAR(3), nullable=False),
        sa.Column("as_of", sa.Date, nullable=False),
        sa.UniqueConstraint("security_id", "as_of"),
    )

    # ── fx_rates ──────────────────────────────────────────────────────────────
    op.create_table(
        "fx_rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("base_currency", sa.CHAR(3), nullable=False),
        sa.Column("quote_currency", sa.CHAR(3), nullable=False),
        sa.Column("rate", sa.Numeric(20, 10), nullable=False),
        sa.Column("as_of", sa.Date, nullable=False, index=True),
        sa.UniqueConstraint("base_currency", "quote_currency", "as_of"),
    )

    # ── portfolio_snapshots ───────────────────────────────────────────────────
    op.create_table(
        "portfolio_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "investor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("investors.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("as_of", sa.Date, nullable=False),
        sa.Column("total_value_amount", sa.Numeric(20, 4), nullable=False),
        sa.Column("total_value_currency", sa.CHAR(3), nullable=False),
        sa.Column(
            "net_external_flow_amount",
            sa.Numeric(20, 4),
            nullable=False,
            server_default="0",
        ),
        sa.UniqueConstraint("investor_id", "as_of"),
    )

    # ── snapshot_holdings ─────────────────────────────────────────────────────
    op.create_table(
        "snapshot_holdings",
        sa.Column(
            "snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("portfolio_snapshots.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "security_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("securities.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("quantity", sa.Numeric(20, 8), nullable=False),
        sa.Column("price_amount", sa.Numeric(20, 4), nullable=False),
        sa.Column("price_currency", sa.CHAR(3), nullable=False),
        sa.Column("fx_rate", sa.Numeric(20, 10), nullable=False, server_default="1"),
        sa.Column("value_amount", sa.Numeric(20, 4), nullable=False),
        sa.Column("value_currency", sa.CHAR(3), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("snapshot_holdings")
    op.drop_table("portfolio_snapshots")
    op.drop_table("fx_rates")
    op.drop_table("prices")
    op.drop_table("holdings")
    op.drop_table("securities")
    op.drop_table("accounts")
    op.drop_table("linked_account_connections")
    op.drop_table("investors")
    op.execute("DROP TYPE IF EXISTS asset_class_enum")
    op.execute("DROP TYPE IF EXISTS account_type")
    op.execute("DROP TYPE IF EXISTS connection_status")
