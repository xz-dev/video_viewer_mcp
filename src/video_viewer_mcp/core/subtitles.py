"""Subtitle reading - supports both downloaded videos and subtitle-only downloads."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from .download import get_video_path
from ..config import get_download_dir

# Default languages downloaded with video (to avoid 429 errors)
DEFAULT_SUBTITLE_LANGS = {"zh-hans", "zh-hant", "zh", "en"}


def _url_to_hash(url: str) -> str:
    """Generate a hash from URL for folder naming."""
    return hashlib.sha256(url.encode()).hexdigest()[:12]


def _get_subtitle_dir(url: str) -> Path:
    """Get the directory for subtitles based on URL hash."""
    url_hash = _url_to_hash(url)
    return get_download_dir() / url_hash


def get_subtitles(
    url: str,
    language: str | None = None,
) -> dict[str, Any]:
    """
    Get subtitles for a video URL.

    Downloads subtitles automatically if not already available.
    Does NOT require the video to be downloaded first.

    Args:
        url: Video URL
        language: Preferred language code (optional)

    Returns:
        dict with subtitle entries
    """
    # First check if video is downloaded (subtitles would be in same directory)
    video_path = get_video_path(url)

    if video_path:
        # Video exists, look for subtitles in video directory
        subtitle_dir = video_path.parent
        search_path = video_path
    else:
        # No video downloaded, use subtitle-only directory
        subtitle_dir = _get_subtitle_dir(url)
        # Create a dummy path for _find_subtitle_files to work
        search_path = subtitle_dir / "video.mp4"

    # Try to find existing subtitle files
    if subtitle_dir.exists():
        subtitle_files = _find_subtitle_files(search_path, language)
    else:
        subtitle_files = []

    # If no subtitles found, try to download them
    if not subtitle_files:
        # Download subtitles (without downloading video)
        if _download_subtitles_directly(url, subtitle_dir, language):
            subtitle_files = _find_subtitle_files(search_path, language)

    # If still no subtitles and a specific language was requested, try on-demand
    if not subtitle_files and language and language.lower() not in DEFAULT_SUBTITLE_LANGS:
        if _download_subtitle_on_demand(url, subtitle_dir, language):
            subtitle_files = _find_subtitle_files(search_path, language)

    if not subtitle_files:
        # Check if there are subtitles in other languages
        all_subtitle_files = _find_subtitle_files(search_path, None) if subtitle_dir.exists() else []
        if all_subtitle_files and language:
            available_langs = _get_available_languages(all_subtitle_files)
            return {
                "success": False,
                "error": f"No subtitles found for language '{language}'. "
                         f"Available languages: {', '.join(available_langs)}",
                "available_languages": available_langs,
            }

        # No local subtitles found - query remote for available languages
        remote_langs = _get_remote_subtitle_languages(url)
        if remote_langs:
            return {
                "success": False,
                "error": "No subtitles available in default languages. "
                         f"Available languages from video: {', '.join(remote_langs)}. "
                         "Request a specific language to download.",
                "available_languages": remote_langs,
            }

        return {
            "success": False,
            "error": "No subtitle files found. The video may not have subtitles.",
        }

    # Parse the first matching subtitle file
    subtitle_file = subtitle_files[0]
    try:
        entries = _parse_subtitle_file(subtitle_file)
        detected_lang = _detect_language_from_filename(subtitle_file)

        return {
            "success": True,
            "language": detected_lang,
            "file": str(subtitle_file),
            "entries": entries,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to parse subtitle file: {e}",
        }


def _download_subtitles_directly(
    url: str, output_dir: Path, language: str | None = None
) -> bool:
    """
    Download subtitles without downloading the video.

    Args:
        url: Video URL
        output_dir: Directory to save subtitles
        language: Optional specific language to download

    Returns:
        True if subtitles were downloaded successfully
    """
    try:
        from ..config.downloaders import download_subtitles_only

        languages = [language] if language else None
        return download_subtitles_only(url, output_dir, languages)
    except Exception:
        return False


def _download_subtitle_on_demand(url: str, output_dir: Path, language: str) -> bool:
    """Download a subtitle language on-demand."""
    try:
        from ..config.downloaders import download_subtitle_on_demand
        return download_subtitle_on_demand(url, output_dir, language)
    except Exception:
        return False


def _get_remote_subtitle_languages(url: str) -> list[str]:
    """
    Query available subtitle languages from the video without downloading.

    Returns a list of language codes available for the video.
    """
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
                return []

            languages = set()

            # Manual subtitles (human-created)
            subtitles = info.get("subtitles", {})
            languages.update(subtitles.keys())

            # Automatic subtitles (auto-generated)
            auto_subs = info.get("automatic_captions", {})
            languages.update(auto_subs.keys())

            # Sort with common languages first
            priority = ["zh-Hans", "zh-Hant", "zh", "en", "ja", "ko"]
            result = []
            for lang in priority:
                if lang in languages:
                    result.append(lang)
                    languages.discard(lang)
            result.extend(sorted(languages))

            return result
    except Exception:
        return []


def _find_subtitle_files(video_path: Path, language: str | None = None) -> list[Path]:
    """Find subtitle files for a video."""
    parent = video_path.parent
    stem = video_path.stem

    # Look for subtitle files with patterns like:
    # - video.en.vtt
    # - video.zh-Hans.srt
    # - video.vtt
    patterns = [
        f"{stem}*.vtt",
        f"{stem}*.srt",
    ]

    files = []
    for pattern in patterns:
        files.extend(parent.glob(pattern))

    # Filter out the video file itself
    files = [f for f in files if f.suffix.lower() in (".vtt", ".srt")]

    # If language is specified, filter to only matching files
    if language:
        lang_lower = language.lower()
        # Filter files to only those containing the language code
        matching_files = [f for f in files if f".{lang_lower}." in f.name.lower()]
        return sorted(matching_files, key=lambda f: f.name)
    else:
        # Default priority: zh-Hans, zh, en, then others
        priority = ["zh-hans", "zh", "en"]

        def get_priority(f: Path) -> tuple[int, str]:
            name_lower = f.name.lower()
            for i, lang in enumerate(priority):
                if f".{lang}." in name_lower:
                    return (i, f.name)
            return (len(priority), f.name)

        files.sort(key=get_priority)

    return files


def _get_available_languages(subtitle_files: list[Path]) -> list[str]:
    """Extract available language codes from subtitle filenames."""
    languages = []
    for f in subtitle_files:
        lang = _detect_language_from_filename(f)
        if lang != "unknown" and lang not in languages:
            languages.append(lang)
    return languages if languages else ["unknown"]


def _detect_language_from_filename(path: Path) -> str:
    """Detect language code from subtitle filename."""
    name = path.stem

    # Common patterns: video.en.vtt, video.zh-Hans.srt
    lang_match = re.search(r'\.([a-z]{2}(?:-[A-Za-z]+)?)\s*$', name)
    if lang_match:
        return lang_match.group(1)

    return "unknown"


def _parse_subtitle_file(path: Path) -> list[dict[str, Any]]:
    """Parse a subtitle file (VTT or SRT format)."""
    content = path.read_text(encoding="utf-8", errors="replace")

    if path.suffix.lower() == ".vtt":
        return _parse_vtt(content)
    else:
        return _parse_srt(content)


def _parse_srt(content: str) -> list[dict[str, Any]]:
    """Parse SRT subtitle format."""
    entries = []
    blocks = re.split(r'\n\n+', content.strip())

    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue

        # Parse index
        try:
            index = int(lines[0])
        except ValueError:
            continue

        # Parse timestamp: 00:00:01,000 --> 00:00:05,500
        time_match = re.match(
            r'(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})',
            lines[1]
        )
        if not time_match:
            continue

        h1, m1, s1, ms1, h2, m2, s2, ms2 = time_match.groups()
        start_ms = int(h1) * 3600000 + int(m1) * 60000 + int(s1) * 1000 + int(ms1)
        end_ms = int(h2) * 3600000 + int(m2) * 60000 + int(s2) * 1000 + int(ms2)

        text = '\n'.join(lines[2:])

        entries.append({
            'index': index,
            'start_ms': start_ms,
            'end_ms': end_ms,
            'text': text,
        })

    return entries


def _parse_vtt(content: str) -> list[dict[str, Any]]:
    """Parse VTT subtitle format."""
    entries = []

    # Skip WEBVTT header
    content = re.sub(r'^WEBVTT.*?\n\n', '', content, flags=re.DOTALL)
    blocks = re.split(r'\n\n+', content.strip())

    index = 0
    for block in blocks:
        lines = block.strip().split('\n')
        if not lines:
            continue

        # Find timestamp line
        time_line = None
        text_start = 0
        for i, line in enumerate(lines):
            if '-->' in line:
                time_line = line
                text_start = i + 1
                break

        if not time_line:
            continue

        # Parse timestamp (VTT format: 00:00:00.000 --> 00:00:00.000)
        # Also supports: 00:00.000 --> 00:00.000
        time_match = re.match(
            r'(\d{2}):(\d{2}):(\d{2})[.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[.](\d{3})',
            time_line
        )
        if time_match:
            h1, m1, s1, ms1, h2, m2, s2, ms2 = time_match.groups()
            start_ms = int(h1) * 3600000 + int(m1) * 60000 + int(s1) * 1000 + int(ms1)
            end_ms = int(h2) * 3600000 + int(m2) * 60000 + int(s2) * 1000 + int(ms2)
        else:
            # Try shorter format: 00:00.000
            time_match = re.match(
                r'(\d{2}):(\d{2})[.](\d{3})\s*-->\s*(\d{2}):(\d{2})[.](\d{3})',
                time_line
            )
            if time_match:
                m1, s1, ms1, m2, s2, ms2 = time_match.groups()
                start_ms = int(m1) * 60000 + int(s1) * 1000 + int(ms1)
                end_ms = int(m2) * 60000 + int(s2) * 1000 + int(ms2)
            else:
                continue

        # Get text (clean up VTT tags)
        text_lines = []
        for line in lines[text_start:]:
            # Remove VTT cue settings and tags like <c>, </c>, <00:00:01.000>
            clean_line = re.sub(r'<[^>]+>', '', line)
            if clean_line.strip():
                text_lines.append(clean_line.strip())

        text = ' '.join(text_lines)
        if not text:
            continue

        index += 1
        entries.append({
            'index': index,
            'start_ms': start_ms,
            'end_ms': end_ms,
            'text': text,
        })

    return entries
