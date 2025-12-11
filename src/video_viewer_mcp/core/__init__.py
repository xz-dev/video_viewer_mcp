"""Core functionality for video-viewer-mcp."""

from .download import download_video, get_download_status, get_video_path, list_downloads
from .screenshot import capture_screenshot, save_screenshot
from .subtitles import get_subtitles
from .tokens import (
    delete_bilibili_token,
    delete_youtube_token,
    get_bilibili_token,
    get_bilibili_token_status,
    get_youtube_token,
    get_youtube_token_status,
    set_bilibili_token,
    set_youtube_token,
)

__all__ = [
    "download_video",
    "get_download_status",
    "list_downloads",
    "get_video_path",
    "capture_screenshot",
    "save_screenshot",
    "get_subtitles",
    # Token management
    "set_youtube_token",
    "get_youtube_token",
    "get_youtube_token_status",
    "delete_youtube_token",
    "set_bilibili_token",
    "get_bilibili_token",
    "get_bilibili_token_status",
    "delete_bilibili_token",
]
