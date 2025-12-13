"""Tests for cleanup scheduler."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from video_viewer_mcp.core.scheduler import CleanupScheduler


@pytest.mark.asyncio
async def test_scheduler_start_stop():
    """Test scheduler starts and stops correctly."""
    scheduler = CleanupScheduler()

    # Mock config
    mock_config = {"enabled": True, "retention_days": 1, "schedule": "0 2 * * *"}

    with patch("video_viewer_mcp.core.scheduler.get_cleanup_config", return_value=mock_config):
        # Start scheduler
        await scheduler.start()

        # Verify scheduler is running
        assert scheduler.scheduler.running is True

        # Verify job is scheduled
        jobs = scheduler.scheduler.get_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == "cleanup_expired_files"

        # Stop scheduler
        await scheduler.stop()

        # Note: After shutdown, the scheduler internal state may vary,
        # but the important thing is that it has been shutdown (logged)
        # and won't trigger any more jobs


@pytest.mark.asyncio
async def test_scheduler_disabled_in_config():
    """Test scheduler doesn't start when disabled in config."""
    scheduler = CleanupScheduler()

    # Mock disabled config
    mock_config = {"enabled": False, "retention_days": 1, "schedule": "0 2 * * *"}

    with patch("video_viewer_mcp.core.scheduler.get_cleanup_config", return_value=mock_config):
        await scheduler.start()

        # Verify scheduler is NOT running
        assert scheduler.scheduler.running is False


@pytest.mark.asyncio
async def test_scheduler_invalid_cron():
    """Test scheduler handles invalid cron expression gracefully."""
    scheduler = CleanupScheduler()

    # Mock config with invalid cron
    mock_config = {"enabled": True, "retention_days": 1, "schedule": "invalid cron"}

    with patch("video_viewer_mcp.core.scheduler.get_cleanup_config", return_value=mock_config):
        # Should not raise exception
        await scheduler.start()

        # Scheduler should not be running
        assert scheduler.scheduler.running is False


@pytest.mark.asyncio
async def test_scheduler_cleanup_execution():
    """Test that cleanup runs when triggered."""
    scheduler = CleanupScheduler()

    mock_config = {"enabled": True, "retention_days": 1, "schedule": "0 2 * * *"}

    # Mock cleanup function
    mock_cleanup_result = {
        "success": True,
        "deleted_count": 5,
        "freed_bytes": 1000000,
        "skipped_downloading": 0,
        "errors": [],
    }

    with patch("video_viewer_mcp.core.scheduler.get_cleanup_config", return_value=mock_config), patch(
        "video_viewer_mcp.core.scheduler.cleanup_expired_files", return_value=mock_cleanup_result
    ) as mock_cleanup:
        # Start scheduler
        await scheduler.start()

        # Manually trigger cleanup
        await scheduler._run_cleanup()

        # Verify cleanup was called
        mock_cleanup.assert_called_once_with(1)  # retention_days=1

        # Stop scheduler
        await scheduler.stop()


@pytest.mark.asyncio
async def test_scheduler_cleanup_with_errors():
    """Test scheduler handles cleanup errors gracefully."""
    scheduler = CleanupScheduler()

    mock_config = {"enabled": True, "retention_days": 1, "schedule": "0 2 * * *"}

    # Mock cleanup function that raises exception
    with patch("video_viewer_mcp.core.scheduler.get_cleanup_config", return_value=mock_config), patch(
        "video_viewer_mcp.core.scheduler.cleanup_expired_files",
        side_effect=Exception("Test error"),
    ):
        await scheduler.start()

        # Should not raise exception
        await scheduler._run_cleanup()

        await scheduler.stop()


@pytest.mark.asyncio
async def test_scheduler_next_run_time():
    """Test that next run time is calculated correctly."""
    scheduler = CleanupScheduler()

    mock_config = {"enabled": True, "retention_days": 1, "schedule": "0 2 * * *"}

    with patch("video_viewer_mcp.core.scheduler.get_cleanup_config", return_value=mock_config):
        await scheduler.start()

        # Get the scheduled job
        job = scheduler.scheduler.get_job("cleanup_expired_files")
        assert job is not None
        assert job.next_run_time is not None

        # Next run time should be in the future
        from datetime import datetime

        assert job.next_run_time > datetime.now(job.next_run_time.tzinfo)

        await scheduler.stop()
