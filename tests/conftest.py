"""Pytest configuration with cached video fixture."""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "data"
TEST_VIDEO_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use default event loop policy."""
    return asyncio.DefaultEventLoopPolicy()


def pytest_configure(config):
    """Configure pytest-asyncio and custom markers."""
    config.addinivalue_line("markers", "asyncio: mark test as async")
    config.addinivalue_line(
        "markers", "network: marks tests as requiring network access"
    )


@pytest.fixture
def cached_youtube_video(tmp_path, monkeypatch):
    """Pre-populate cache directory to simulate already-downloaded YouTube video.

    This fixture creates the necessary job files and video directory structure
    so that the code thinks the video is already downloaded (cached).

    Use this fixture for tests that need a downloaded video but don't want to
    make real network requests.
    """
    url = TEST_VIDEO_URL
    job_id = hashlib.sha256(url.encode()).hexdigest()[:12]

    # Setup directories
    data_dir = tmp_path / "data"
    download_dir = tmp_path / "downloads"
    video_dir = download_dir / job_id
    jobs_dir = data_dir / "jobs"

    for d in [data_dir, jobs_dir, video_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # Create job file (required for get_video_dir_by_url to return the directory)
    job_file = jobs_dir / f"{job_id}.json"
    job_file.write_text(
        json.dumps(
            {
                "job_id": job_id,
                "url": url,
                "status": "completed",
                "progress": 100.0,
                "started_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "output_path": str(video_dir / "video.mp4"),
                "error": None,
            },
            indent=2,
        )
    )

    # Create URL index (maps URL to job_id)
    index_file = data_dir / "url_index.json"
    index_file.write_text(json.dumps({url: job_id}, indent=2))

    # Copy fixture files to video directory
    fixture_dir = FIXTURES_DIR / "youtube" / "jNQXAC9IVRw"
    shutil.copy(fixture_dir / "video.mp4", video_dir / "video.mp4")
    shutil.copy(fixture_dir / "metadata.json", video_dir / "metadata.json")

    # Monkeypatch environment variables to use temp directories
    monkeypatch.setenv("VIDEO_MCP_DATA_DIR", str(data_dir))
    monkeypatch.setenv("VIDEO_MCP_DOWNLOAD_DIR", str(download_dir))

    return {
        "url": url,
        "job_id": job_id,
        "video_dir": video_dir,
        "data_dir": data_dir,
        "download_dir": download_dir,
    }
