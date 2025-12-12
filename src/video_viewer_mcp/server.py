"""MCP server for video-viewer-mcp using FastMCP."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.utilities.types import Image as McpImage
from mcp.server.transport_security import TransportSecuritySettings

from .config import ensure_dirs
from .core import (
    download_video,
    get_danmaku,
    get_download_status,
    get_subtitles,
    get_video_path,
    get_video_metadata,
    list_downloads,
    # Token management
    set_youtube_token,
    get_youtube_token_status,
    delete_youtube_token,
    set_bilibili_token,
    get_bilibili_token_status,
    delete_bilibili_token,
)
from .core.screenshot import capture_screenshot

# Create FastMCP server instance
# Disable DNS rebinding protection to allow any Host header (for Docker/reverse proxy)
mcp = FastMCP(
    "video-viewer-mcp",
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


@mcp.tool(name="video_viewer_download_video")
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


@mcp.tool(name="video_viewer_get_download_status")
def tool_get_download_status(job_id: str) -> dict:
    """
    Get the status of a download job by job ID.

    Args:
        job_id: The job ID returned from download_video
    """
    return get_download_status(job_id)


@mcp.tool(name="video_viewer_list_downloads")
def tool_list_downloads(status: str | None = None) -> dict:
    """
    List all download jobs.

    Args:
        status: Filter by status (started, downloading, completed, failed)
    """
    return list_downloads(status)


@mcp.tool(name="video_viewer_get_subtitles")
def tool_get_subtitles(url: str, language: str | None = None) -> dict:
    """
    Get subtitles for a video URL.

    Video must be downloaded first. Reads subtitle files downloaded by yt-dlp.

    Args:
        url: Video URL (must be downloaded first)
        language: Preferred language code (e.g., 'en', 'zh')
    """
    return get_subtitles(url, language)


@mcp.tool(name="video_viewer_get_danmaku")
def tool_get_danmaku(
    url: str,
    start_time: float | None = None,
    end_time: float | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict:
    """
    Get danmaku (bullet comments) for a Bilibili video with pagination.

    Video must be downloaded first. Reads danmaku XML file downloaded by BBDown.

    Args:
        url: Video URL (must be downloaded first)
        start_time: Filter start time in seconds (optional)
        end_time: Filter end time in seconds (optional)
        page: Page number, 1-indexed (default 1)
        page_size: Number of items per page (default 100)
    """
    return get_danmaku(url, start_time, end_time, page, page_size)


@mcp.tool(name="video_viewer_screenshot")
def tool_screenshot(
    url: str,
    timestamp: str,
    width: int | None = None,
    height: int | None = None,
):
    """
    Capture a frame from a video at specified timestamp.

    Video must be downloaded first. Returns the image.

    Auto-scaling: If no width is specified, videos wider than 1280px will be
    scaled down to 1280px width (720p). Videos 1280px or narrower are returned
    at original resolution.

    Args:
        url: Video URL (must be downloaded first)
        timestamp: Timestamp as seconds (e.g., '123.45') or HH:MM:SS format
        width: Resize width (optional, auto-scales to 1280 max if not specified)
        height: Resize height (optional)
    """
    video_path = get_video_path(url)
    if not video_path:
        return {"error": "Video not downloaded. Use download_video first."}

    # Auto-scale logic: if no width specified, scale down videos > 1280px wide
    if width is None:
        metadata = get_video_metadata(url)
        if metadata and metadata.get("width"):
            video_width = metadata["width"]
            if video_width > 1280:
                width = 1280
            # else: width stays None, original resolution is used

    try:
        image_bytes, mime_type = capture_screenshot(
            video_path, timestamp, width, height
        )
        # Return McpImage which FastMCP will convert to ImageContent
        image_format = mime_type.split("/")[1]  # "image/png" -> "png"
        return McpImage(data=image_bytes, format=image_format)
    except Exception as e:
        return {"error": f"Error capturing screenshot: {e}"}


# Token management tools


@mcp.tool(name="video_viewer_set_youtube_token")
def tool_set_youtube_token(cookies: list[dict[str, Any]]) -> dict:
    """
    Set YouTube cookies for authenticated downloads.

    Use this to download members-only or age-restricted videos.

    Args:
        cookies: List of cookie dicts in browser export format.
                 To get cookies:
                 1. Install browser extension "Get cookies.txt LOCALLY"
                 2. Login to youtube.com
                 3. Export cookies as JSON (not txt)
                 4. Pass the JSON array here
                 Each cookie should have: name, value, domain, path, etc.
                 Example: [{"name": "LOGIN_INFO", "value": "...", "domain": ".youtube.com"}]
    """
    ensure_dirs()
    return set_youtube_token(cookies)


@mcp.tool(name="video_viewer_get_youtube_token")
def tool_get_youtube_token() -> dict:
    """
    Get YouTube token status.

    Returns whether a token exists and when it was last updated.
    Does not return sensitive cookie values.
    """
    return get_youtube_token_status()


@mcp.tool(name="video_viewer_delete_youtube_token")
def tool_delete_youtube_token() -> dict:
    """
    Delete YouTube token.

    Removes stored YouTube cookies.
    """
    return delete_youtube_token()


@mcp.tool(name="video_viewer_set_bilibili_token")
def tool_set_bilibili_token(
    sessdata: str | None = None,
    access_key: str | None = None,
) -> dict:
    """
    Set Bilibili token for authenticated downloads.

    Use this to download VIP-only videos or higher quality streams.
    At least one of sessdata or access_key must be provided.

    Args:
        sessdata: SESSDATA cookie value from browser. To get it:
                  1. Login to bilibili.com
                  2. Open DevTools (F12) -> Application -> Cookies
                  3. Find cookie named "SESSDATA" and copy its value
                  Note: Only pass the value, not "SESSDATA=xxx"
        access_key: Access key from Bilibili APP (for APP API authentication)
    """
    ensure_dirs()
    return set_bilibili_token(sessdata, access_key)


@mcp.tool(name="video_viewer_get_bilibili_token")
def tool_get_bilibili_token() -> dict:
    """
    Get Bilibili token status.

    Returns whether sessdata and/or access_key are configured.
    Does not return sensitive token values.
    """
    return get_bilibili_token_status()


@mcp.tool(name="video_viewer_delete_bilibili_token")
def tool_delete_bilibili_token() -> dict:
    """
    Delete Bilibili token.

    Removes stored Bilibili authentication tokens.
    """
    return delete_bilibili_token()
