"""Scheduler for cleanup tasks."""

from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..config import get_cleanup_config
from .cleanup import cleanup_expired_files

logger = logging.getLogger(__name__)


class CleanupScheduler:
    """
    Manages scheduled cleanup tasks using APScheduler.

    Lifecycle:
    - start(): Initialize scheduler and add cleanup job
    - stop(): Gracefully shutdown scheduler
    """

    def __init__(self):
        """Initialize the scheduler."""
        self.scheduler = AsyncIOScheduler()
        self._job_id = "cleanup_expired_files"

    async def start(self):
        """Start the scheduler with current config."""
        config = get_cleanup_config()

        if not config["enabled"]:
            logger.info("Cleanup scheduler disabled in config")
            return

        # Parse cron expression
        schedule = config["schedule"]
        try:
            trigger = CronTrigger.from_crontab(schedule)
        except ValueError as e:
            logger.error(f"Invalid cron expression '{schedule}': {e}")
            return

        # Add cleanup job
        self.scheduler.add_job(
            self._run_cleanup,
            trigger=trigger,
            id=self._job_id,
            replace_existing=True,
            max_instances=1,  # Prevent concurrent runs
        )

        self.scheduler.start()

        # Log next run time
        job = self.scheduler.get_job(self._job_id)
        if job:
            next_run = job.next_run_time
            logger.info(f"Cleanup scheduler started, next run: {next_run}")
        else:
            logger.warning("Cleanup scheduler started but job not found")

    async def _run_cleanup(self):
        """Execute cleanup (internal wrapper with logging)."""
        config = get_cleanup_config()
        retention_days = config["retention_days"]

        logger.info(f"Starting scheduled cleanup (retention: {retention_days} days)")

        try:
            # Run cleanup in thread pool to avoid blocking event loop
            result = await asyncio.to_thread(cleanup_expired_files, retention_days)

            if result["success"]:
                freed_mb = result["freed_bytes"] / 1024 / 1024
                logger.info(
                    f"Cleanup completed: {result['deleted_count']} folders deleted, "
                    f"{freed_mb:.2f} MB freed"
                )

                if result["skipped_downloading"] > 0:
                    logger.info(f"Skipped {result['skipped_downloading']} folders with downloads in progress")

                if result["errors"]:
                    logger.warning(f"Cleanup had {len(result['errors'])} errors:")
                    for error in result["errors"]:
                        logger.warning(f"  - {error['folder']}: {error['error']}")
            else:
                logger.warning(f"Cleanup completed with errors: {result['errors']}")

        except Exception as e:
            logger.error(f"Cleanup failed with exception: {e}", exc_info=True)

    async def stop(self):
        """Stop the scheduler gracefully."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=True)
            logger.info("Cleanup scheduler stopped")
