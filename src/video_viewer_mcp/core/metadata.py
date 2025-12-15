"""Video metadata extraction without downloading."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .download import get_video_dir_by_url, _load_metadata

logger = logging.getLogger(__name__)

# Default fields returned in metadata responses (optimized for AI context understanding)
DEFAULT_METADATA_FIELDS = {
    # Identification
    "id",
    # Content understanding (core)
    "title", "description", "duration", "chapters",
    # Source/author
    "uploader", "channel", "upload_date",
    # Video properties
    "width", "height", "thumbnail",
    # Statistics (reflects content quality/popularity)
    "view_count", "like_count", "comment_count",
    # Content classification
    "categories", "tags",
    # Subtitle availability (helps AI decide which subtitle to request)
    "available_subtitles",
}


def _extract_default_fields(info: dict) -> dict:
    """Extract default fields from video info.

    Args:
        info: Full video info dict from yt-dlp

    Returns:
        Dict containing only the default fields
    """
    result = {}
    for key in DEFAULT_METADATA_FIELDS:
        if key == "available_subtitles":
            # Extract available subtitle languages
            subtitles = info.get("subtitles", {})
            auto_captions = info.get("automatic_captions", {})
            if subtitles or auto_captions:
                result[key] = {
                    "manual": sorted(subtitles.keys()) if subtitles else [],
                    "auto": sorted(auto_captions.keys()) if auto_captions else [],
                }
        elif key in info and info[key] is not None:
            result[key] = info[key]
    return result


def _extract_fields_by_path(info: dict, paths: list[str]) -> dict:
    """Extract additional fields using dot notation paths.

    Supported path formats:
    - "formats" -> returns full formats array
    - "formats.resolution" -> returns resolution from each format element
    - "subtitles.en" -> returns English subtitle data

    Args:
        info: Full video info dict
        paths: List of field paths to extract

    Returns:
        Dict with extracted fields (keys use underscore notation like formats_resolution)
    """
    result = {}
    for path in paths:
        parts = path.split(".")
        if len(parts) == 1:
            # Top-level field
            if parts[0] in info:
                result[parts[0]] = info[parts[0]]
        elif len(parts) == 2:
            field, subfield = parts
            if field in info and info[field]:
                if isinstance(info[field], list):
                    # Array type (e.g., formats): extract subfield from each element
                    result[f"{field}_{subfield}"] = [
                        item.get(subfield) for item in info[field] if subfield in item
                    ]
                elif isinstance(info[field], dict):
                    # Dict type (e.g., subtitles): extract specific key
                    if subfield in info[field]:
                        result[f"{field}_{subfield}"] = info[field][subfield]
    return result


def query_video_info(
    url: str,
    extra_fields: list[str] | None = None,
) -> dict[str, Any]:
    """
    Query video metadata without downloading.

    Returns concise metadata by default (optimized for AI context understanding).
    Use extra_fields to request additional data.

    Default fields: id, title, description, duration, chapters, uploader,
    channel, upload_date, width, height, thumbnail, view_count, like_count,
    comment_count, categories, tags

    Args:
        url: Video URL (supports YouTube, Twitter, Bilibili, Vimeo, etc.)
        extra_fields: Additional fields to include using dot notation.
                     Examples: ["formats", "formats.resolution", "subtitles"]

    Returns:
        dict with:
        - success: bool - True if query succeeded
        - cached: bool - True if loaded from local download
        - data: dict - Metadata fields (if success=True)
        - error: str - Error message (if success=False)
    """
    # Check if video is already downloaded
    video_dir = get_video_dir_by_url(url)
    if video_dir:
        full_metadata = _load_metadata(video_dir)
        if full_metadata:
            # Apply same filtering as remote query
            data = _extract_default_fields(full_metadata)
            if extra_fields:
                data.update(_extract_fields_by_path(full_metadata, extra_fields))
            return {
                "success": True,
                "cached": True,
                "data": data,
            }

    # Query remote metadata using yt-dlp
    import yt_dlp
    from ..config.downloaders import get_cookies_file_for_url

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }

    # Add cookies if available (supports YouTube, Bilibili, etc.)
    cookies_file = get_cookies_file_for_url(url)
    if cookies_file:
        ydl_opts["cookiefile"] = str(cookies_file)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            if not info:
                return {
                    "success": False,
                    "error": "Could not extract video info from URL"
                }

            # Extract default fields only
            data = _extract_default_fields(info)

            # Add extra fields if requested
            if extra_fields:
                data.update(_extract_fields_by_path(info, extra_fields))

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
    finally:
        # Clean up temp cookies file
        if cookies_file and cookies_file.exists():
            cookies_file.unlink()
