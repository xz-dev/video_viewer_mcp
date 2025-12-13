"""File cleanup functionality for video-viewer-mcp."""

from __future__ import annotations

import json
import logging
import shutil
import time
from pathlib import Path
from typing import Any

from ..config import get_data_dir, get_download_dir

logger = logging.getLogger(__name__)


def get_folder_age_days(folder_path: Path) -> float | None:
    """
    Get folder age in days based on oldest file's mtime.

    Uses the oldest file's modification time to determine folder age.
    This represents the download time (when video was first downloaded).

    Args:
        folder_path: Path to the folder to check

    Returns:
        Age in days, or None if folder is empty or inaccessible
    """
    try:
        files = list(folder_path.rglob("*"))
        if not files:
            return None

        # Get the oldest file's mtime (represents download time)
        oldest_mtime = min(f.stat().st_mtime for f in files if f.is_file())
        age_seconds = time.time() - oldest_mtime
        age_days = age_seconds / 86400.0
        return age_days
    except (OSError, ValueError) as e:
        logger.warning(f"Failed to get age for {folder_path}: {e}")
        return None


def check_job_status(job_id: str) -> str | None:
    """
    Check the status of a download job.

    Args:
        job_id: The job ID to check

    Returns:
        Job status string ("started", "downloading", "completed", "failed"),
        or None if job file doesn't exist or can't be read
    """
    job_file = get_data_dir() / "jobs" / f"{job_id}.json"

    if not job_file.exists():
        return None

    try:
        with open(job_file) as f:
            job_data = json.load(f)
            return job_data.get("status")
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to read job file {job_file}: {e}")
        return None


def delete_video_folder_safe(folder_path: Path) -> tuple[bool, str | None, int]:
    """
    Safely delete a video folder with error handling.

    Args:
        folder_path: Path to the folder to delete

    Returns:
        Tuple of (success, error_message, bytes_freed)
    """
    try:
        # Calculate folder size before deletion
        folder_size = sum(f.stat().st_size for f in folder_path.rglob("*") if f.is_file())

        # Delete the folder
        shutil.rmtree(folder_path)

        return True, None, folder_size

    except PermissionError as e:
        # File may be in use or insufficient permissions
        error_msg = f"Permission denied: {e}"
        logger.warning(f"Skipped {folder_path}: {error_msg}")
        return False, error_msg, 0

    except OSError as e:
        # Retry once after brief delay
        logger.debug(f"Retrying delete for {folder_path} after error: {e}")
        time.sleep(0.1)

        try:
            folder_size = sum(f.stat().st_size for f in folder_path.rglob("*") if f.is_file())
            shutil.rmtree(folder_path)
            return True, None, folder_size
        except Exception as retry_error:
            error_msg = f"Failed after retry: {retry_error}"
            logger.error(f"Failed to delete {folder_path}: {error_msg}")
            return False, error_msg, 0

    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        logger.error(f"Failed to delete {folder_path}: {error_msg}")
        return False, error_msg, 0


def cleanup_orphaned_metadata(deleted_job_ids: set[str]) -> dict[str, int]:
    """
    Clean up job files and URL index entries for deleted folders.

    Args:
        deleted_job_ids: Set of job IDs that have been deleted

    Returns:
        Dictionary with cleanup statistics
    """
    deleted_jobs = 0
    cleaned_index_entries = 0

    # Delete job files
    jobs_dir = get_data_dir() / "jobs"
    for job_id in deleted_job_ids:
        job_file = jobs_dir / f"{job_id}.json"
        try:
            if job_file.exists():
                job_file.unlink()
                deleted_jobs += 1
        except OSError as e:
            logger.warning(f"Failed to delete job file {job_file}: {e}")

    # Clean up url_index.json
    url_index_file = get_data_dir() / "url_index.json"
    if url_index_file.exists():
        try:
            with open(url_index_file) as f:
                url_index = json.load(f)

            # Remove entries pointing to deleted job IDs
            original_size = len(url_index)
            url_index = {
                url: job_id
                for url, job_id in url_index.items()
                if job_id not in deleted_job_ids
            }
            cleaned_index_entries = original_size - len(url_index)

            # Write back
            with open(url_index_file, "w") as f:
                json.dump(url_index, f, indent=2)

        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to clean url_index.json: {e}")

    return {
        "deleted_jobs": deleted_jobs,
        "cleaned_index_entries": cleaned_index_entries,
    }


def cleanup_expired_files(retention_days: int) -> dict[str, Any]:
    """
    Clean up expired download files based on retention period.

    Process:
    1. Scan all folders in DOWNLOAD_DIR
    2. For each folder:
       - Check all files' mtime (modification time)
       - Use the NEWEST file's mtime as folder age
       - Check job status (skip if downloading/started)
       - If folder age > retention_days and status is completed/failed: mark for deletion
    3. Delete marked folders (entire folder including all files)
    4. Clean up orphaned job files in DATA_DIR/jobs/
    5. Clean up orphaned entries in url_index.json

    Args:
        retention_days: Number of days to retain files

    Returns:
        Dictionary with cleanup statistics:
        {
            "success": True,
            "deleted_count": 5,
            "freed_bytes": 1234567890,
            "skipped_downloading": 2,
            "errors": [],
            "details": [...]
        }
    """
    download_dir = get_download_dir()

    if not download_dir.exists():
        logger.info(f"Download directory does not exist: {download_dir}")
        return {
            "success": True,
            "deleted_count": 0,
            "freed_bytes": 0,
            "skipped_downloading": 0,
            "errors": [],
            "details": [],
        }

    deleted_count = 0
    freed_bytes = 0
    skipped_downloading = 0
    errors = []
    details = []
    deleted_job_ids = set()

    # Scan all folders
    for folder in download_dir.iterdir():
        if not folder.is_dir():
            continue

        folder_name = folder.name

        # Calculate folder age
        age_days = get_folder_age_days(folder)
        if age_days is None:
            logger.debug(f"Skipped {folder_name}: unable to determine age")
            continue

        # Check if folder should be deleted
        if age_days <= retention_days:
            logger.debug(f"Skipped {folder_name}: age {age_days:.2f} days <= retention {retention_days} days")
            continue

        # Check job status (folder name = job_id)
        job_id = folder_name
        job_status = check_job_status(job_id)

        # Skip if job is still in progress
        if job_status in ("started", "downloading"):
            logger.info(f"Skipped {folder_name}: job status is {job_status}")
            skipped_downloading += 1
            continue

        # Skip if job file doesn't exist (might be initializing)
        if job_status is None:
            logger.debug(f"Skipped {folder_name}: job status unknown")
            continue

        # Job is completed or failed, safe to delete
        logger.info(f"Deleting {folder_name}: age {age_days:.2f} days, status {job_status}")

        success, error_msg, size = delete_video_folder_safe(folder)

        if success:
            deleted_count += 1
            freed_bytes += size
            deleted_job_ids.add(job_id)
            details.append({
                "folder": folder_name,
                "age_days": round(age_days, 2),
                "size_bytes": size,
                "status": job_status,
            })
        else:
            errors.append({
                "folder": folder_name,
                "error": error_msg,
            })

    # Clean up orphaned metadata
    if deleted_job_ids:
        metadata_stats = cleanup_orphaned_metadata(deleted_job_ids)
        logger.info(
            f"Cleaned up metadata: {metadata_stats['deleted_jobs']} jobs, "
            f"{metadata_stats['cleaned_index_entries']} index entries"
        )

    return {
        "success": True,
        "deleted_count": deleted_count,
        "freed_bytes": freed_bytes,
        "skipped_downloading": skipped_downloading,
        "errors": errors,
        "details": details,
    }
