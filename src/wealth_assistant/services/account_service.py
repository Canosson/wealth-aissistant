"""Account service: data export and cascading account deletion (T025, FR-017/018)."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from wealth_assistant.persistence.models import Investor
from wealth_assistant.persistence.repositories import (
    ConnectionRepository,
    InvestorRepository,
    SnapshotRepository,
)


class AccountService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def export_investor_data(self, investor: Investor) -> dict[str, Any]:
        """Return a portable JSON-safe representation of all investor data (FR-017)."""
        conn_repo = ConnectionRepository(self._session)
        snap_repo = SnapshotRepository(self._session)

        connections = await conn_repo.list_by_investor(investor.id)
        snapshots = await snap_repo.list_by_investor(investor.id)

        return {
            "investor_id": str(investor.id),
            "email": investor.email,
            "reporting_currency": investor.reporting_currency,
            "created_at": investor.created_at.isoformat(),
            "connections": [
                {
                    "id": str(c.id),
                    "provider": c.provider,
                    "institution_name": c.institution_name,
                    "status": c.status.value,
                    "last_synced_at": (
                        c.last_synced_at.isoformat() if c.last_synced_at else None
                    ),
                }
                for c in connections
            ],
            "snapshot_count": len(snapshots),
        }

    async def delete_investor(self, investor_id: uuid.UUID) -> None:
        """Delete investor and all associated data via DB cascade (FR-018, SC-009)."""
        repo = InvestorRepository(self._session)
        investor = await repo.get_by_id(investor_id)
        if investor is not None:
            await repo.delete(investor)
