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

# Create FastMCP server instance
# Disable DNS rebinding protection to allow any Host header (for Docker/reverse proxy)
mcp = FastMCP(
    "video-viewer-mcp",
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)

# =============================================================================
# TOOL USAGE GUIDANCE FOR AI ASSISTANTS:
#
# To understand video content:
#   1. get_video_info     → Metadata (title, description, duration, stats)
#   2. download_video     → Required for subtitles (limitation)
#   3. get_subtitles      → Full transcript/captions
#
# To capture screenshots:
#   1. get_video_info     → Check video details/resolution
#   2. download_video     → Download video file
#   3. screenshot         → Capture frame at timestamp
#
# Downloads are EXPENSIVE (bandwidth, storage, time). Only download when
# screenshots are actually needed. Metadata + subtitles are usually sufficient
# for content understanding.
# =============================================================================


@mcp.tool(name="video_viewer_download_video")
def tool_download_video(url: str, output_dir: str | None = None) -> dict:
    """
    Download a video from URL - ONLY needed for taking screenshots.

    IMPORTANT: Only download the video if you need to capture screenshots at
    specific timestamps. For understanding video content, you can use:
    - get_video_info: Get metadata (title, duration, description, etc.)
    - get_subtitles: Get subtitles/transcripts (video must be downloaded first)

    Downloads the video file to disk and also extracts subtitles/danmaku if available.

    Use Cases:
    - Need screenshots at specific timestamps -> Download required
    - Only need to understand content -> Use get_video_info + get_subtitles instead
    - Only checking video details -> Use get_video_info only

    Returns download status. If already downloaded, returns existing job info with
    metadata.

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
    Get subtitles/transcripts for a video URL.

    Current limitation: Video must be downloaded first, even though subtitles
    could technically be downloaded separately. Use this with download_video to get
    subtitles for understanding video content.

    Workflow for understanding video content WITHOUT screenshots:
    1. get_video_info - Check title, description, available subtitle languages
    2. download_video - Download video (also downloads subtitles)
    3. get_subtitles - Read subtitle content

    Note: Default languages (zh/en) are downloaded automatically. Other languages
    are downloaded on-demand when requested.

    Args:
        url: Video URL (must be downloaded first)
        language: Preferred language code (e.g., 'en', 'zh', 'ja', 'ko')

    Returns:
        Dictionary with subtitle entries or available languages if requested language
        is not found
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

    This is the PRIMARY reason to download a video. If you don't need screenshots,
    consider using get_video_info + get_subtitles to understand content instead.

    Video must be downloaded first using download_video. Returns the image.

    Workflow:
    1. Use get_video_info to check video details and resolution
    2. Download video using download_video (if screenshots are needed)
    3. Capture screenshot at desired timestamp with this tool

    Auto-scaling: If no dimensions specified, videos with any dimension > 1280px
    will be scaled down so the largest dimension is 1280px. Smaller videos are
    returned at original resolution.

    Args:
        url: Video URL (must be downloaded first)
        timestamp: Timestamp as seconds (e.g., '123.45') or HH:MM:SS format
        width: Resize width (optional, auto-scales to 1280 max if not specified)
        height: Resize height (optional)
    """
    video_path = get_video_path(url)
    if not video_path:
        return {"error": "Video not downloaded. Use download_video first."}

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


@mcp.tool(name="video_viewer_get_video_info")
def tool_get_video_info(url: str) -> dict:
    """
    Query detailed video metadata without downloading - PREFERRED for understanding video content.

    Use this FIRST before considering download_video. Most information needs can be
    satisfied with metadata alone.

    Returns ALL available metadata about a video including title, duration,
    uploader, resolution, formats/qualities, available subtitles, description,
    view count, and 100+ other fields from yt-dlp.

    Use this to:
    - Understand video content (title, description, duration)
    - Check available subtitle/caption languages
    - Verify video quality/resolution options
    - Get uploader information and statistics
    - Check if subtitles are available before downloading

    Combined with get_subtitles, you can fully understand video content without
    downloading the video file. Only download_video if screenshots are needed.

    Args:
        url: Video URL (YouTube, Twitter, Bilibili, Vimeo, etc.)

    Returns:
        Dictionary with success status, cached flag, and all video metadata including:
        - Basic: title, description, duration, upload_date
        - Media: width, height, resolution, formats
        - Content: subtitles (available languages), chapters
        - Statistics: view_count, like_count, comment_count
        - 100+ additional fields
    """
    return query_video_info(url)
