"""APScheduler bootstrap for background jobs (T029).

Jobs (e.g. weekly portfolio snapshot) are registered by individual modules
under scheduler/jobs.py and added via `register_jobs()` before starting.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    """Return the shared scheduler instance, creating it on first call."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="UTC")
    return _scheduler


def register_jobs() -> None:
    """Register recurring jobs. Call once before start().

    The weekly snapshot job stays unregistered while SNAPSHOT_JOB_ENABLED is
    false (the default) so it cannot write history before the snapshot
    pipeline is validated end-to-end.
    """
    from apscheduler.triggers.cron import CronTrigger

    from wealth_assistant.config import get_settings
    from wealth_assistant.scheduler.jobs import weekly_snapshot_job

    if not get_settings().snapshot_job_enabled:
        logger.warning("weekly_snapshot job NOT registered (snapshot_job_enabled=False)")
        return

    sched = get_scheduler()
    sched.add_job(weekly_snapshot_job, CronTrigger(day_of_week="tue", hour=2, timezone="UTC"), id="weekly_snapshot", replace_existing=True)


def start() -> None:
    """Start the scheduler if it is not already running."""
    sched = get_scheduler()
    register_jobs()
    if not sched.running:
        sched.start()
        logger.info("APScheduler started")


def shutdown(wait: bool = True) -> None:
    """Shut down the scheduler gracefully."""
    sched = get_scheduler()
    if sched.running:
        sched.shutdown(wait=wait)
        logger.info("APScheduler stopped")
