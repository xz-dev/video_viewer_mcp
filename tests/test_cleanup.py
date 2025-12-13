"""Tests for cleanup functionality."""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from video_viewer_mcp.core.cleanup import (
    check_job_status,
    cleanup_expired_files,
    cleanup_orphaned_metadata,
    delete_video_folder_safe,
    get_folder_age_days,
)


@pytest.fixture
def temp_dirs():
    """Create temporary directories for testing."""
    with tempfile.TemporaryDirectory() as download_dir, tempfile.TemporaryDirectory() as data_dir:
        # Create jobs directory
        jobs_dir = Path(data_dir) / "jobs"
        jobs_dir.mkdir()
        yield {"download_dir": Path(download_dir), "data_dir": Path(data_dir), "jobs_dir": jobs_dir}


def test_get_folder_age_days_oldest_file():
    """Test folder age calculation based on oldest file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_folder = Path(tmpdir) / "test"
        test_folder.mkdir()

        # Create oldest file (2 days ago)
        old_file = test_folder / "video.mp4"
        old_file.write_text("old video")
        old_time = time.time() - (2 * 86400)  # 2 days ago
        os.utime(old_file, (old_time, old_time))

        # Create newer file (1 hour ago)
        new_file = test_folder / "subtitle.vtt"
        new_file.write_text("new subtitle")
        new_time = time.time() - 3600  # 1 hour ago
        os.utime(new_file, (new_time, new_time))

        # Test - should return age based on oldest file
        age = get_folder_age_days(test_folder)
        assert age is not None
        assert 1.9 < age < 2.1, f"Expected age ~2 days, got {age}"


def test_get_folder_age_days_empty_folder():
    """Test empty folder handling."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_folder = Path(tmpdir) / "empty"
        test_folder.mkdir()

        age = get_folder_age_days(test_folder)
        assert age is None


def test_get_folder_age_days_nonexistent():
    """Test nonexistent folder handling."""
    nonexistent = Path("/nonexistent/folder")
    age = get_folder_age_days(nonexistent)
    assert age is None


def test_check_job_status_completed(temp_dirs):
    """Test reading completed status."""
    job_id = "test_job_completed"
    job_file = temp_dirs["jobs_dir"] / f"{job_id}.json"

    # Create job file with completed status
    job_data = {
        "job_id": job_id,
        "url": "https://example.com/video",
        "status": "completed",
        "progress": 100.0,
    }
    with open(job_file, "w") as f:
        json.dump(job_data, f)

    # Mock get_data_dir to return our temp directory
    with patch("video_viewer_mcp.core.cleanup.get_data_dir", return_value=temp_dirs["data_dir"]):
        status = check_job_status(job_id)
        assert status == "completed"


def test_check_job_status_downloading(temp_dirs):
    """Test reading downloading status."""
    job_id = "test_job_downloading"
    job_file = temp_dirs["jobs_dir"] / f"{job_id}.json"

    # Create job file with downloading status
    job_data = {
        "job_id": job_id,
        "url": "https://example.com/video",
        "status": "downloading",
        "progress": 50.0,
    }
    with open(job_file, "w") as f:
        json.dump(job_data, f)

    with patch("video_viewer_mcp.core.cleanup.get_data_dir", return_value=temp_dirs["data_dir"]):
        status = check_job_status(job_id)
        assert status == "downloading"


def test_check_job_status_missing_file(temp_dirs):
    """Test job file doesn't exist."""
    with patch("video_viewer_mcp.core.cleanup.get_data_dir", return_value=temp_dirs["data_dir"]):
        status = check_job_status("nonexistent_job")
        assert status is None


def test_delete_video_folder_safe_success():
    """Test successful folder deletion."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_folder = Path(tmpdir) / "test"
        test_folder.mkdir()

        # Create test files
        (test_folder / "video.mp4").write_text("video content" * 100)
        (test_folder / "subtitle.vtt").write_text("subtitle content")

        # Delete folder
        success, error, bytes_freed = delete_video_folder_safe(test_folder)

        assert success is True
        assert error is None
        assert bytes_freed > 0
        assert not test_folder.exists()


def test_delete_video_folder_safe_nonexistent():
    """Test deleting nonexistent folder."""
    nonexistent = Path("/tmp/nonexistent_folder_12345")
    success, error, bytes_freed = delete_video_folder_safe(nonexistent)

    assert success is False
    assert error is not None
    assert bytes_freed == 0


def test_cleanup_orphaned_metadata(temp_dirs):
    """Test metadata cleanup."""
    # Create test job files
    job_ids = {"job1", "job2"}
    for job_id in job_ids:
        job_file = temp_dirs["jobs_dir"] / f"{job_id}.json"
        job_file.write_text("{}")

    # Create url_index.json
    url_index_file = temp_dirs["data_dir"] / "url_index.json"
    url_index = {
        "https://example.com/video1": "job1",
        "https://example.com/video2": "job2",
        "https://example.com/video3": "job3",  # Should be kept
    }
    with open(url_index_file, "w") as f:
        json.dump(url_index, f)

    # Mock get_data_dir
    with patch("video_viewer_mcp.core.cleanup.get_data_dir", return_value=temp_dirs["data_dir"]):
        result = cleanup_orphaned_metadata(job_ids)

    # Verify results
    assert result["deleted_jobs"] == 2
    assert result["cleaned_index_entries"] == 2

    # Verify job files deleted
    assert not (temp_dirs["jobs_dir"] / "job1.json").exists()
    assert not (temp_dirs["jobs_dir"] / "job2.json").exists()

    # Verify url_index updated
    with open(url_index_file) as f:
        updated_index = json.load(f)
    assert len(updated_index) == 1
    assert "https://example.com/video3" in updated_index


def test_cleanup_expired_files_respects_retention(temp_dirs):
    """Test retention period is respected."""
    download_dir = temp_dirs["download_dir"]
    data_dir = temp_dirs["data_dir"]
    jobs_dir = temp_dirs["jobs_dir"]

    # Create folder A: 3 days old, completed (should be deleted)
    folder_a = download_dir / "folder_a"
    folder_a.mkdir()
    file_a = folder_a / "video.mp4"
    file_a.write_text("video a")
    old_time = time.time() - (3 * 86400)
    os.utime(file_a, (old_time, old_time))

    job_a = jobs_dir / "folder_a.json"
    job_a.write_text(json.dumps({"status": "completed"}))

    # Create folder B: 0.5 days old, completed (should be kept)
    folder_b = download_dir / "folder_b"
    folder_b.mkdir()
    file_b = folder_b / "video.mp4"
    file_b.write_text("video b")
    recent_time = time.time() - (0.5 * 86400)
    os.utime(file_b, (recent_time, recent_time))

    job_b = jobs_dir / "folder_b.json"
    job_b.write_text(json.dumps({"status": "completed"}))

    # Create folder C: 2 days old, downloading (should be skipped)
    folder_c = download_dir / "folder_c"
    folder_c.mkdir()
    file_c = folder_c / "video.mp4"
    file_c.write_text("video c")
    mid_time = time.time() - (2 * 86400)
    os.utime(file_c, (mid_time, mid_time))

    job_c = jobs_dir / "folder_c.json"
    job_c.write_text(json.dumps({"status": "downloading"}))

    # Run cleanup with 1 day retention
    with patch("video_viewer_mcp.core.cleanup.get_download_dir", return_value=download_dir), patch(
        "video_viewer_mcp.core.cleanup.get_data_dir", return_value=data_dir
    ):
        result = cleanup_expired_files(retention_days=1)

    # Verify results
    assert result["success"] is True
    assert result["deleted_count"] == 1  # Only A
    assert result["skipped_downloading"] == 1  # C

    # Verify folders
    assert not folder_a.exists()  # Deleted
    assert folder_b.exists()  # Kept (too recent)
    assert folder_c.exists()  # Kept (downloading)


def test_cleanup_expired_files_empty_download_dir():
    """Test cleanup with nonexistent download directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        nonexistent_dir = Path(tmpdir) / "nonexistent"

        with patch("video_viewer_mcp.core.cleanup.get_download_dir", return_value=nonexistent_dir):
            result = cleanup_expired_files(retention_days=1)

        assert result["success"] is True
        assert result["deleted_count"] == 0
        assert result["errors"] == []


def test_cleanup_expired_files_skips_downloading(temp_dirs):
    """Test that downloading files are never deleted."""
    download_dir = temp_dirs["download_dir"]
    data_dir = temp_dirs["data_dir"]
    jobs_dir = temp_dirs["jobs_dir"]

    # Create old folder with downloading status
    folder = download_dir / "downloading_folder"
    folder.mkdir()
    video_file = folder / "video.mp4"
    video_file.write_text("video content")

    # Make it old (5 days)
    old_time = time.time() - (5 * 86400)
    os.utime(video_file, (old_time, old_time))

    # Set status to downloading
    job_file = jobs_dir / "downloading_folder.json"
    job_file.write_text(json.dumps({"status": "downloading"}))

    # Run cleanup with 1 day retention
    with patch("video_viewer_mcp.core.cleanup.get_download_dir", return_value=download_dir), patch(
        "video_viewer_mcp.core.cleanup.get_data_dir", return_value=data_dir
    ):
        result = cleanup_expired_files(retention_days=1)

    # Verify folder was NOT deleted
    assert result["deleted_count"] == 0
    assert result["skipped_downloading"] == 1
    assert folder.exists()


def test_cleanup_expired_files_skips_started_status(temp_dirs):
    """Test that started files are never deleted."""
    download_dir = temp_dirs["download_dir"]
    data_dir = temp_dirs["data_dir"]
    jobs_dir = temp_dirs["jobs_dir"]

    # Create old folder with started status
    folder = download_dir / "started_folder"
    folder.mkdir()
    video_file = folder / "video.mp4"
    video_file.write_text("video content")

    old_time = time.time() - (5 * 86400)
    os.utime(video_file, (old_time, old_time))

    job_file = jobs_dir / "started_folder.json"
    job_file.write_text(json.dumps({"status": "started"}))

    with patch("video_viewer_mcp.core.cleanup.get_download_dir", return_value=download_dir), patch(
        "video_viewer_mcp.core.cleanup.get_data_dir", return_value=data_dir
    ):
        result = cleanup_expired_files(retention_days=1)

    # Verify folder was NOT deleted
    assert result["deleted_count"] == 0
    assert result["skipped_downloading"] == 1
    assert folder.exists()
