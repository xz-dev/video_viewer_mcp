"""Data models for video-viewer-mcp."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Download job status."""

    STARTED = "started"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"


class DownloadJob(BaseModel):
    """A download job."""

    job_id: str
    url: str
    status: JobStatus
    progress: float = 0.0
    started_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    output_path: str | None = None
    error: str | None = None


class SubtitleEntry(BaseModel):
    """A single subtitle entry."""

    index: int
    start_ms: int
    end_ms: int
    text: str


class SubtitleResult(BaseModel):
    """Result from subtitle extraction."""

    success: bool
    language: str | None = None
    entries: list[SubtitleEntry] = Field(default_factory=list)
    error: str | None = None
