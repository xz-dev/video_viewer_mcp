"""MCP server for video-viewer-mcp using FastMCP."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import ensure_dirs
from .core import (
    download_video,
    get_download_status,
    get_subtitles,
    get_video_path,
    list_downloads,
    # Token management
    set_youtube_token,
    get_youtube_token_status,
    delete_youtube_token,
    set_bilibili_token,
    get_bilibili_token_status,
    delete_bilibili_token,
)
from .core.screenshot import capture_screenshot_base64

# Create FastMCP server instance
mcp = FastMCP("video-viewer-mcp")


@mcp.tool()
def tool_download_video(url: str, output_dir: str | None = None) -> dict:
    """
    Download a video from URL.

    Returns download status. If already downloaded, returns existing job info.

    Args:
        url: Video URL to download
        output_dir: Output directory (optional)
    """
    ensure_dirs()
    return download_video(url, output_dir)


@mcp.tool()
def tool_get_download_status(job_id: str) -> dict:
    """
    Get the status of a download job by job ID.

    Args:
        job_id: The job ID returned from download_video
    """
    return get_download_status(job_id)


@mcp.tool()
def tool_list_downloads(status: str | None = None) -> dict:
    """
    List all download jobs.

    Args:
        status: Filter by status (started, downloading, completed, failed)
    """
    return list_downloads(status)


@mcp.tool()
def tool_get_subtitles(url: str, language: str | None = None) -> dict:
    """
    Get subtitles for a video URL.

    Video must be downloaded first. Reads subtitle files downloaded by yt-dlp.

    Args:
        url: Video URL (must be downloaded first)
        language: Preferred language code (e.g., 'en', 'zh')
    """
    return get_subtitles(url, language)


@mcp.tool()
def tool_screenshot(
    url: str,
    timestamp: str,
    width: int | None = 1280,
    height: int | None = None,
) -> str | dict:
    """
    Capture a frame from a video at specified timestamp.

    Video must be downloaded first. Returns the image as base64.

    Args:
        url: Video URL (must be downloaded first)
        timestamp: Timestamp as seconds (e.g., '123.45') or HH:MM:SS format
        width: Resize width (optional, default 1280)
        height: Resize height (optional)
    """
    video_path = get_video_path(url)
    if not video_path:
        return {"error": "Video not downloaded. Use download_video first."}

    try:
        base64_data, mime_type = capture_screenshot_base64(
            video_path, timestamp, width, height
        )
        return {
            "data": base64_data,
            "mime_type": mime_type,
        }
    except Exception as e:
        return {"error": f"Error capturing screenshot: {e}"}


# Token management tools


@mcp.tool()
def tool_set_youtube_token(cookies: list[dict[str, Any]]) -> dict:
    """
    Set YouTube cookies for authenticated downloads.

    Use this to download members-only or age-restricted videos.

    Args:
        cookies: List of cookie dicts in browser export format.
                 Each cookie should have: name, value, domain, path, etc.
                 Example: [{"name": "LOGIN_INFO", "value": "...", "domain": ".youtube.com"}]
    """
    ensure_dirs()
    return set_youtube_token(cookies)


@mcp.tool()
def tool_get_youtube_token() -> dict:
    """
    Get YouTube token status.

    Returns whether a token exists and when it was last updated.
    Does not return sensitive cookie values.
    """
    return get_youtube_token_status()


@mcp.tool()
def tool_delete_youtube_token() -> dict:
    """
    Delete YouTube token.

    Removes stored YouTube cookies.
    """
    return delete_youtube_token()


@mcp.tool()
def tool_set_bilibili_token(
    sessdata: str | None = None,
    access_key: str | None = None,
) -> dict:
    """
    Set Bilibili token for authenticated downloads.

    Use this to download VIP-only videos or higher quality streams.
    At least one of sessdata or access_key must be provided.

    Args:
        sessdata: SESSDATA cookie value from browser (for web authentication)
        access_key: Access key from Bilibili APP (for APP API authentication)
    """
    ensure_dirs()
    return set_bilibili_token(sessdata, access_key)


@mcp.tool()
def tool_get_bilibili_token() -> dict:
    """
    Get Bilibili token status.

    Returns whether sessdata and/or access_key are configured.
    Does not return sensitive token values.
    """
    return get_bilibili_token_status()


@mcp.tool()
def tool_delete_bilibili_token() -> dict:
    """
    Delete Bilibili token.

    Removes stored Bilibili authentication tokens.
    """
    return delete_bilibili_token()
