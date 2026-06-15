"""T044: Weekly (Tuesday) snapshot job registered with APScheduler (FR-016)."""
from __future__ import annotations

import structlog

from wealth_assistant.persistence.db import AsyncSessionFactory
from wealth_assistant.services.snapshot_service import SnapshotService

log = structlog.get_logger(__name__)


async def weekly_snapshot_job() -> None:
    """Take a portfolio snapshot for every investor. Runs weekly on Tuesdays."""
    async with AsyncSessionFactory() as session:
        service = SnapshotService(session)
        count = await service.snapshot_all_investors()
        await session.commit()
    log.info("weekly_snapshot_complete", investors_snapshotted=count)
