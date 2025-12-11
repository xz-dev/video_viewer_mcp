"""
Downloader configuration - URL matching and download implementations.

This is "code as configuration" - modify this file to customize download behavior.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse


def match_downloader(url: str) -> str:
    """
    Match URL to a downloader name.

    Modify this function to add custom URL matching logic.

    Args:
        url: Video URL

    Returns:
        Downloader name (currently only "yt-dlp" is supported)
    """
    host = urlparse(url).netloc.lower()

    # YouTube
    if "youtube.com" in host or "youtu.be" in host:
        return "yt-dlp"

    # Bilibili -> BBDown
    if "bilibili.com" in host or "b23.tv" in host:
        return "bbdown"

    # Twitter/X
    if "twitter.com" in host or "x.com" in host:
        return "yt-dlp"

    # Vimeo
    if "vimeo.com" in host:
        return "yt-dlp"

    # Default: yt-dlp supports many websites
    return "yt-dlp"


def download_video(
    url: str,
    output_dir: Path,
    job_id: str,
    progress_callback: Callable[[float, str], None] | None = None,
) -> dict[str, Any]:
    """
    Download video using the matched downloader.

    Args:
        url: Video URL
        output_dir: Output directory
        job_id: Job ID for tracking
        progress_callback: Optional callback(progress_percent, status_message)

    Returns:
        dict with success, output_path, title, etc.
    """
    downloader = match_downloader(url)

    if downloader == "yt-dlp":
        return _download_with_ytdlp(url, output_dir, job_id, progress_callback)
    elif downloader == "bbdown":
        return _download_with_bbdown(url, output_dir, job_id, progress_callback)
    else:
        return {
            "success": False,
            "error": f"Unknown downloader: {downloader}",
        }


def _get_youtube_cookies() -> list[dict[str, Any]] | None:
    """Get YouTube cookies from token storage."""
    # Import here to avoid circular imports
    from ..core.tokens import get_youtube_token

    token = get_youtube_token()
    if token.get("exists") and token.get("cookies"):
        return token["cookies"]
    return None


def _get_bilibili_token() -> dict[str, Any]:
    """Get Bilibili token from token storage."""
    # Import here to avoid circular imports
    from ..core.tokens import get_bilibili_token

    return get_bilibili_token()


def _write_cookies_file(cookies: list[dict[str, Any]]) -> Path:
    """
    Write cookies to a Netscape format cookies file for yt-dlp.

    Args:
        cookies: List of cookie dicts

    Returns:
        Path to temporary cookies file
    """
    # Create temp file that won't be auto-deleted
    fd, path = tempfile.mkstemp(suffix=".txt", prefix="yt_cookies_")

    lines = ["# Netscape HTTP Cookie File"]
    for cookie in cookies:
        # Netscape format: domain, flag, path, secure, expiry, name, value
        domain = cookie.get("domain", "")
        flag = "TRUE" if domain.startswith(".") else "FALSE"
        path_val = cookie.get("path", "/")
        secure = "TRUE" if cookie.get("secure", False) else "FALSE"
        expiry = str(int(cookie.get("expirationDate", 0)))
        name = cookie.get("name", "")
        value = cookie.get("value", "")

        lines.append(f"{domain}\t{flag}\t{path_val}\t{secure}\t{expiry}\t{name}\t{value}")

    import os
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(lines))

    return Path(path)


def _download_with_ytdlp(
    url: str,
    output_dir: Path,
    job_id: str,
    progress_callback: Callable[[float, str], None] | None = None,
) -> dict[str, Any]:
    """
    Download video and subtitles using yt-dlp.

    Args:
        url: Video URL
        output_dir: Output directory
        job_id: Job ID for tracking
        progress_callback: Optional callback for progress updates

    Returns:
        dict with download result
    """
    import yt_dlp

    output_dir.mkdir(parents=True, exist_ok=True)
    # Use simple filename to avoid "File name too long" errors
    output_template = str(output_dir / "video.%(ext)s")

    # Progress hook for yt-dlp
    def progress_hook(d: dict[str, Any]) -> None:
        if progress_callback is None:
            return

        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            if total > 0:
                percent = (downloaded / total) * 100
                progress_callback(percent, "downloading")
        elif d["status"] == "finished":
            progress_callback(100, "processing")

    ydl_opts: dict[str, Any] = {
        "outtmpl": {
            "default": output_template,
            "subtitle": str(output_dir / "video.%(ext)s"),
        },
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["all"],
        "subtitlesformat": "vtt/srt/best",
        "progress_hooks": [progress_hook],
        "quiet": True,
        "no_warnings": True,
    }

    # Add cookies if available
    cookies_file: Path | None = None
    cookies = _get_youtube_cookies()
    if cookies:
        cookies_file = _write_cookies_file(cookies)
        ydl_opts["cookiefile"] = str(cookies_file)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info is None:
                return {
                    "success": False,
                    "error": "Failed to extract video info",
                }

            output_path = ydl.prepare_filename(info)

            # Save metadata to info.json
            video_info = {
                "title": info.get("title"),
                "duration": info.get("duration"),
                "uploader": info.get("uploader"),
                "url": url,
                "video_file": Path(output_path).name,
            }
            info_path = output_dir / "info.json"
            info_path.write_text(json.dumps(video_info, ensure_ascii=False, indent=2))

            return {
                "success": True,
                "output_path": output_path,
                **video_info,
            }

    except yt_dlp.utils.DownloadError as e:
        return {
            "success": False,
            "error": str(e),
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Download failed: {e}",
        }
    finally:
        # Clean up temp cookies file
        if cookies_file and cookies_file.exists():
            cookies_file.unlink()


def _download_with_bbdown(
    url: str,
    output_dir: Path,
    job_id: str,
    progress_callback: Callable[[float, str], None] | None = None,
) -> dict[str, Any]:
    """
    Download video and subtitles using BBDown (for Bilibili).

    Args:
        url: Video URL
        output_dir: Output directory
        job_id: Job ID for tracking
        progress_callback: Optional callback for progress updates

    Returns:
        dict with download result
    """
    # Check if BBDown is installed
    if shutil.which("BBDown") is None:
        return {
            "success": False,
            "error": "BBDown not installed. Install with: dotnet tool install --global BBDown",
        }

    output_dir.mkdir(parents=True, exist_ok=True)

    # Build BBDown command - use simple filename to avoid "File name too long" errors
    cmd = [
        "BBDown",
        url,
        "--work-dir", str(output_dir),
        "--file-pattern", "video",
        "--download-danmaku", "True",
    ]

    # Add authentication if available
    token = _get_bilibili_token()
    if token.get("exists"):
        if token.get("sessdata"):
            cmd.extend(["-c", f"SESSDATA={token['sessdata']}"])
        if token.get("access_key"):
            cmd.extend(["--access-token", token["access_key"]])

    try:
        if progress_callback:
            progress_callback(0, "starting")

        # Run BBDown
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(output_dir),
        )

        if result.returncode != 0:
            return {
                "success": False,
                "error": f"BBDown failed: {result.stderr or result.stdout}",
            }

        # Parse output to find downloaded file and title
        output_path = _parse_bbdown_output(result.stdout, output_dir)
        title = _parse_bbdown_title(result.stdout)

        # Check for subtitles and download AI subtitles if none found
        _download_ai_subtitles_if_needed(url, output_dir, token)

        if progress_callback:
            progress_callback(100, "completed")

        # Save metadata to info.json
        video_info = {
            "title": title,
            "url": url,
            "video_file": output_path.name if output_path else None,
        }
        info_path = output_dir / "info.json"
        info_path.write_text(json.dumps(video_info, ensure_ascii=False, indent=2))

        return {
            "success": True,
            "output_path": str(output_path) if output_path else None,
            **video_info,
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"BBDown download failed: {e}",
        }


def _parse_bbdown_output(stdout: str, output_dir: Path) -> Path | None:
    """
    Parse BBDown output to find the downloaded video file.

    Args:
        stdout: BBDown stdout output
        output_dir: Output directory

    Returns:
        Path to downloaded video file, or None if not found
    """
    # Look for video files in output directory
    video_extensions = [".mp4", ".mkv", ".flv", ".webm"]

    # Find the most recently created video file
    video_files = []
    for ext in video_extensions:
        video_files.extend(output_dir.glob(f"*{ext}"))

    if not video_files:
        return None

    # Return the most recently modified file
    return max(video_files, key=lambda f: f.stat().st_mtime)


def _parse_bbdown_title(stdout: str) -> str | None:
    """
    Parse BBDown output to extract video title.

    BBDown output typically contains a line like:
    视频标题: <title>

    Args:
        stdout: BBDown stdout output

    Returns:
        Video title, or None if not found
    """
    import re

    # Try to match "视频标题: xxx" pattern
    match = re.search(r"视频标题[:：]\s*(.+)", stdout)
    if match:
        return match.group(1).strip()

    # Try to match "Title: xxx" pattern (English)
    match = re.search(r"Title[:：]\s*(.+)", stdout, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    return None


def _download_ai_subtitles_if_needed(
    url: str,
    output_dir: Path,
    token: dict,
) -> None:
    """
    Check if subtitles exist and download AI subtitles if none found.

    BBDown skips AI subtitles by default. If no regular subtitles are available,
    this function runs BBDown again with --sub-only to fetch AI subtitles.

    Authentication methods (if token provided):
    - SESSDATA: Web cookie authentication (recommended, easier to obtain)
    - access_key: APP API authentication (alternative method)

    Args:
        url: Video URL
        output_dir: Output directory
        token: Bilibili authentication token dict (may contain sessdata and/or access_key)
    """
    # Check for existing subtitle files
    subtitle_files = list(output_dir.glob("*.srt")) + list(output_dir.glob("*.ass"))

    if subtitle_files:
        # Subtitles already exist, no need to download AI subtitles
        return

    # No subtitles found, try to download AI subtitles
    ai_cmd = [
        "BBDown",
        url,
        "--work-dir", str(output_dir),
        "--sub-only",  # Only download subtitles
        # Note: not passing --skip-ai means AI subtitles will be downloaded
    ]

    # Add authentication if available
    if token.get("exists"):
        if token.get("sessdata"):
            ai_cmd.extend(["-c", f"SESSDATA={token['sessdata']}"])
        if token.get("access_key"):
            ai_cmd.extend(["--access-token", token["access_key"]])

    # Run BBDown for AI subtitles (ignore errors - this is optional)
    subprocess.run(
        ai_cmd,
        capture_output=True,
        text=True,
        cwd=str(output_dir),
    )
