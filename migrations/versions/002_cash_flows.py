"""Add cash_flows table for net external flows ledger.

Revision ID: 002
Revises: 001
Create Date: 2026-06-13

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cash_flows",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("investor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(20, 4), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["investor_id"], ["investors.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cash_flows_investor_id", "cash_flows", ["investor_id"])
    op.create_index("ix_cash_flows_occurred_on", "cash_flows", ["occurred_on"])


def downgrade() -> None:
    op.drop_index("ix_cash_flows_occurred_on", table_name="cash_flows")
    op.drop_index("ix_cash_flows_investor_id", table_name="cash_flows")
    op.drop_table("cash_flows")
