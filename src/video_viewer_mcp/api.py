"""REST API routes for video-viewer-mcp."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query, Body
from fastapi.responses import Response
from pydantic import BaseModel

from .config import ensure_dirs
from .core import (
    download_video,
    get_danmaku,
    get_download_status,
    get_subtitles,
    get_video_path,
    get_video_metadata,
    list_downloads,
    query_video_info,
    # Token management
    set_youtube_token,
    get_youtube_token_status,
    delete_youtube_token,
    set_bilibili_token,
    get_bilibili_token_status,
    delete_bilibili_token,
)
from .core.screenshot import capture_screenshot

router = APIRouter()


# Pydantic models for request bodies
class YouTubeTokenRequest(BaseModel):
    """Request body for setting YouTube token."""
    cookies: list[dict[str, Any]]


class BilibiliTokenRequest(BaseModel):
    """Request body for setting Bilibili token."""
    sessdata: str | None = None
    access_key: str | None = None


@router.get("/health")
async def health():
    """Health check and service info."""
    return {
        "name": "video-viewer-mcp",
        "version": "0.1.0",
        "status": "healthy",
        "endpoints": {
            "api": "/api",
            "mcp": "/mcp",
            "docs": "/docs",
        },
    }


@router.post("/download")
async def api_download(
    url: Annotated[str, Query(description="Video URL to download")],
    output_dir: Annotated[str | None, Query(description="Output directory")] = None,
):
    """Download a video from URL."""
    ensure_dirs()
    return download_video(url, output_dir)


@router.get("/download/{job_id}")
async def api_status(job_id: str):
    """Get download status by job ID."""
    return get_download_status(job_id)


@router.get("/downloads")
async def api_list(
    status: Annotated[
        str | None,
        Query(description="Filter by status (started, downloading, completed, failed)"),
    ] = None,
):
    """List all download jobs."""
    return list_downloads(status)


@router.get("/video-info")
async def api_video_info(
    url: Annotated[
        str,
        Query(description="Video URL to query metadata for (YouTube, Twitter, Bilibili, etc.)")
    ]
) -> dict:
    """
    Query detailed video metadata without downloading.

    Returns comprehensive metadata including title, duration, resolution,
    uploader, formats, subtitles, and 100+ other fields from yt-dlp.

    Use this endpoint to:
    - Inspect video details before downloading
    - Check available subtitle languages
    - Verify video quality/resolution options
    - Get description, statistics, etc.

    If the video is already downloaded, returns cached metadata instantly.
    Otherwise queries the remote video source using yt-dlp.

    Args:
        url: Video URL (supports YouTube, Twitter, Bilibili, Vimeo, etc.)

    Returns:
        {
            "success": bool,
            "cached": bool,
            "data": {
                "title": str,
                "duration": int,
                "width": int,
                "height": int,
                ... (100+ fields)
            }
        }
    """
    return query_video_info(url)


@router.get("/subtitles")
async def api_subtitles(
    url: Annotated[str, Query(description="Video URL (must be downloaded first)")],
    language: Annotated[str | None, Query(description="Preferred language code")] = None,
):
    """Get subtitles for a video URL."""
    return get_subtitles(url, language)


@router.get("/screenshot")
async def api_screenshot(
    url: Annotated[str, Query(description="Video URL (must be downloaded first)")],
    timestamp: Annotated[str, Query(description="Timestamp (seconds or HH:MM:SS)")],
    width: Annotated[int | None, Query(description="Resize width (auto-scales to 1280 max if not specified)")] = None,
    height: Annotated[int | None, Query(description="Resize height")] = None,
):
    """Capture a frame from a video at specified timestamp.

    Auto-scaling: If no dimensions specified, videos with any dimension > 1280px
    will be scaled down so the largest dimension is 1280px. Smaller videos are
    returned at original resolution.
    """
    video_path = get_video_path(url)
    if not video_path:
        return {"success": False, "error": "Video not downloaded. Use /api/download first."}

    # Auto-scale logic: if no dimensions specified, scale down videos with max dimension > 1280px
    if width is None and height is None:
        metadata = get_video_metadata(url)
        if metadata:
            video_width = metadata.get("width")
            video_height = metadata.get("height")
            if video_width and video_height:
                max_dimension = max(video_width, video_height)
                if max_dimension > 1280:
                    if video_width >= video_height:
                        width = 1280
                    else:
                        height = 1280

    try:
        image_bytes, mime_type = capture_screenshot(video_path, timestamp, width, height)

        return Response(
            content=image_bytes,
            media_type=mime_type,
        )
    except Exception as e:
        return {"success": False, "error": f"Error capturing screenshot: {e}"}


@router.get("/danmaku")
async def api_danmaku(
    url: Annotated[str, Query(description="Video URL (must be downloaded first)")],
    start_time: Annotated[float | None, Query(description="Filter start time in seconds")] = None,
    end_time: Annotated[float | None, Query(description="Filter end time in seconds")] = None,
    page: Annotated[int, Query(description="Page number (1-indexed)", ge=1)] = 1,
    page_size: Annotated[int, Query(description="Items per page", ge=1, le=1000)] = 100,
):
    """Get danmaku (bullet comments) for a Bilibili video with pagination."""
    return get_danmaku(url, start_time, end_time, page, page_size)


# Token management endpoints


@router.post("/tokens/youtube")
async def api_set_youtube_token(request: YouTubeTokenRequest):
    """
    Set YouTube cookies for authenticated downloads.

    Request body:
    ```json
    {
      "cookies": [
        {"name": "LOGIN_INFO", "value": "...", "domain": ".youtube.com", ...}
      ]
    }
    ```
    """
    ensure_dirs()
    return set_youtube_token(request.cookies)


@router.get("/tokens/youtube")
async def api_get_youtube_token():
    """Get YouTube token status (does not return sensitive cookie values)."""
    return get_youtube_token_status()


@router.delete("/tokens/youtube")
async def api_delete_youtube_token():
    """Delete YouTube token."""
    return delete_youtube_token()


@router.post("/tokens/bilibili")
async def api_set_bilibili_token(request: BilibiliTokenRequest):
    """
    Set Bilibili token (SESSDATA and/or access_key).

    Request body:
    ```json
    {
      "sessdata": "xxx",
      "access_key": "yyy"
    }
    ```

    At least one of sessdata or access_key must be provided.
    """
    ensure_dirs()
    return set_bilibili_token(request.sessdata, request.access_key)


@router.get("/tokens/bilibili")
async def api_get_bilibili_token():
    """Get Bilibili token status (does not return sensitive token values)."""
    return get_bilibili_token_status()


@router.delete("/tokens/bilibili")
async def api_delete_bilibili_token():
    """Delete Bilibili token."""
    return delete_bilibili_token()
