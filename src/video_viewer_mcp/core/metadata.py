"""Video metadata extraction without downloading."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .download import get_video_dir_by_url, _load_metadata

logger = logging.getLogger(__name__)


def query_video_info(url: str) -> dict[str, Any]:
    """
    Query detailed metadata from a video URL without downloading.

    First checks if video is already downloaded (returns cached metadata).
    If not, queries remote video metadata using yt-dlp without downloading.

    Returns ALL available metadata fields from yt-dlp including:
    - Basic: title, duration, uploader, upload_date
    - Media: width, height, fps, formats (quality options)
    - Content: description, view_count, like_count, comment_count
    - Availability: subtitles, automatic_captions, chapters
    - And 100+ other fields from yt-dlp

    Args:
        url: Video URL (supports YouTube, Twitter, Bilibili, Vimeo, etc.)

    Returns:
        dict with:
        - success: bool - True if query succeeded
        - cached: bool - True if loaded from local download
        - data: dict - All metadata fields (if success=True)
        - error: str - Error message (if success=False)
    """
    # Check if video is already downloaded
    video_dir = get_video_dir_by_url(url)
    if video_dir:
        metadata = _load_metadata(video_dir)
        if metadata:
            return {
                "success": True,
                "cached": True,
                "data": metadata,
            }

    # Query remote metadata using yt-dlp
    try:
        import yt_dlp

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            if not info:
                return {
                    "success": False,
                    "error": "Could not extract video info from URL"
                }

            # Return all fields, removing None values for cleaner output
            data = {k: v for k, v in info.items() if v is not None}

            return {
                "success": True,
                "cached": False,
                "data": data,
            }

    except yt_dlp.utils.DownloadError as e:
        return {
            "success": False,
            "error": f"Invalid URL or unsupported site: {str(e)}"
        }
    except Exception as e:
        logger.error(f"Failed to query video info for {url}: {e}")
        return {
            "success": False,
            "error": f"Failed to query video info: {str(e)}"
        }
