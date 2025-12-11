"""Video download management with URL hash-based folder structure."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ..config import get_data_dir, get_download_dir, download_video as config_download
from ..models import DownloadJob, JobStatus


def _get_jobs_dir() -> Path:
    """Get the jobs directory."""
    jobs_dir = get_data_dir() / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    return jobs_dir


def _get_url_index_file() -> Path:
    """Get the URL index file path."""
    return get_data_dir() / "url_index.json"


def _load_url_index() -> dict[str, str]:
    """Load URL to job_id mapping."""
    index_file = _get_url_index_file()
    if index_file.exists():
        with open(index_file) as f:
            return json.load(f)
    return {}


def _save_url_index(index: dict[str, str]) -> None:
    """Save URL to job_id mapping."""
    index_file = _get_url_index_file()
    index_file.parent.mkdir(parents=True, exist_ok=True)
    with open(index_file, "w") as f:
        json.dump(index, f, indent=2)


def _url_to_hash(url: str) -> str:
    """Generate a hash from URL (used for both job_id and folder name)."""
    return hashlib.sha256(url.encode()).hexdigest()[:12]


def _get_video_dir(url: str) -> Path:
    """
    Get the directory for a video based on URL hash.

    Structure: $DOWNLOAD_DIR/{url_hash}/
    """
    url_hash = _url_to_hash(url)
    video_dir = get_download_dir() / url_hash
    video_dir.mkdir(parents=True, exist_ok=True)
    return video_dir


def _load_job(job_id: str) -> DownloadJob | None:
    """Load a job from disk."""
    job_file = _get_jobs_dir() / f"{job_id}.json"
    if job_file.exists():
        with open(job_file) as f:
            data = json.load(f)
            return DownloadJob(**data)
    return None


def _save_job(job: DownloadJob) -> None:
    """Save a job to disk."""
    job_file = _get_jobs_dir() / f"{job.job_id}.json"
    job_file.parent.mkdir(parents=True, exist_ok=True)
    with open(job_file, "w") as f:
        json.dump(job.model_dump(mode="json"), f, indent=2, default=str)


def _save_metadata(video_dir: Path, metadata: dict[str, Any]) -> None:
    """Save video metadata to the video directory."""
    metadata_file = video_dir / "metadata.json"
    metadata["downloaded_at"] = datetime.now().isoformat()
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)


def _load_metadata(video_dir: Path) -> dict[str, Any] | None:
    """Load video metadata from the video directory."""
    metadata_file = video_dir / "metadata.json"
    if metadata_file.exists():
        with open(metadata_file) as f:
            return json.load(f)
    return None


def get_job_by_url(url: str) -> DownloadJob | None:
    """Get a job by URL if it exists."""
    index = _load_url_index()
    job_id = index.get(url)
    if job_id:
        return _load_job(job_id)
    return None


def get_video_path(url: str) -> Path | None:
    """
    Get the local video path for a URL if download is completed.

    Args:
        url: The video URL

    Returns:
        Path to the local video file, or None if not downloaded
    """
    job = get_job_by_url(url)
    if job and job.status == JobStatus.COMPLETED and job.output_path:
        path = Path(job.output_path)
        if path.exists():
            return path
    return None


def get_video_dir_by_url(url: str) -> Path | None:
    """
    Get the video directory for a URL if download is completed.

    Args:
        url: The video URL

    Returns:
        Path to the video directory, or None if not downloaded
    """
    job = get_job_by_url(url)
    if job and job.status == JobStatus.COMPLETED:
        video_dir = _get_video_dir(url)
        if video_dir.exists():
            return video_dir
    return None


def download_video(
    url: str,
    output_dir: str | None = None,
) -> dict[str, Any]:
    """
    Download a video (blocking).

    If the video was already downloaded successfully, returns existing job info.
    Videos are stored in hash-based folders: $DOWNLOAD_DIR/{url_hash}/

    Args:
        url: Video URL to download
        output_dir: Output directory (optional, defaults to hash-based folder)

    Returns:
        dict with job status information
    """
    # Check if download already exists and completed
    existing_job = get_job_by_url(url)
    if existing_job and existing_job.status == JobStatus.COMPLETED:
        # Verify the file still exists
        if existing_job.output_path and Path(existing_job.output_path).exists():
            return {
                "success": True,
                "job_id": existing_job.job_id,
                "status": existing_job.status.value,
                "progress": 100.0,
            }

    # Generate job ID (same as URL hash)
    job_id = _url_to_hash(url)

    # Use hash-based folder structure
    video_dir = _get_video_dir(url)
    output_path = Path(output_dir) if output_dir else video_dir

    # Create job record
    job = DownloadJob(
        job_id=job_id,
        url=url,
        status=JobStatus.DOWNLOADING,
    )
    _save_job(job)

    # Update URL index
    index = _load_url_index()
    index[url] = job_id
    _save_url_index(index)

    # Progress callback to update job status
    def progress_callback(progress: float, status_msg: str) -> None:
        job.progress = progress
        job.updated_at = datetime.now()
        _save_job(job)

    # Execute download using config/downloaders
    try:
        result = config_download(
            url=url,
            output_dir=output_path,
            job_id=job_id,
            progress_callback=progress_callback,
        )

        if result.get("success"):
            job.status = JobStatus.COMPLETED
            job.progress = 100.0
            job.output_path = result.get("output_path")
            job.updated_at = datetime.now()
            _save_job(job)

            # Save metadata to video directory
            _save_metadata(video_dir, {
                "url": url,
                "title": result.get("title"),
                "duration": result.get("duration"),
                "uploader": result.get("uploader"),
                "output_path": result.get("output_path"),
            })

            return {
                "success": True,
                "job_id": job_id,
                "status": "completed",
                "progress": 100.0,
                "title": result.get("title"),
                "video_dir": str(video_dir),
            }
        else:
            job.status = JobStatus.FAILED
            job.error = result.get("error", "Unknown error")
            job.updated_at = datetime.now()
            _save_job(job)

            return {
                "success": False,
                "job_id": job_id,
                "status": "failed",
                "error": job.error,
            }

    except Exception as e:
        job.status = JobStatus.FAILED
        job.error = str(e)
        job.updated_at = datetime.now()
        _save_job(job)

        return {
            "success": False,
            "job_id": job_id,
            "status": "failed",
            "error": str(e),
        }


def get_download_status(job_id: str) -> dict[str, Any]:
    """
    Get the status of a download job.

    Args:
        job_id: The job ID

    Returns:
        dict with current status and progress
    """
    job = _load_job(job_id)
    if not job:
        return {
            "success": False,
            "error": f"Job not found: {job_id}",
        }

    return {
        "success": job.status != JobStatus.FAILED,
        "job_id": job.job_id,
        "url": job.url,
        "status": job.status.value,
        "progress": job.progress,
        "error": job.error,
    }


def list_downloads(status: str | None = None) -> dict[str, Any]:
    """
    List all download jobs.

    Args:
        status: Filter by status (optional)

    Returns:
        dict with list of jobs
    """
    jobs_dir = _get_jobs_dir()
    jobs = []

    for job_file in jobs_dir.glob("*.json"):
        try:
            with open(job_file) as f:
                job_data = json.load(f)
                job = DownloadJob(**job_data)

                # Filter by status if specified
                if status and job.status.value != status:
                    continue

                jobs.append({
                    "job_id": job.job_id,
                    "url": job.url,
                    "status": job.status.value,
                    "progress": job.progress,
                    "started_at": job.started_at.isoformat() if job.started_at else None,
                })
        except Exception:
            continue

    return {
        "success": True,
        "jobs": jobs,
        "count": len(jobs),
    }
