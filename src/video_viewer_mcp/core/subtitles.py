"""Subtitle reading from downloaded video files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .download import get_video_path


def get_subtitles(
    url: str,
    language: str | None = None,
) -> dict[str, Any]:
    """
    Get subtitles for a video URL by reading downloaded subtitle files.

    yt-dlp downloads subtitles alongside the video file.

    Args:
        url: Video URL
        language: Preferred language code (optional)

    Returns:
        dict with subtitle entries
    """
    # Get the local video path
    video_path = get_video_path(url)
    if not video_path:
        return {
            "success": False,
            "error": "Video not downloaded. Use download_video first.",
        }

    # Find subtitle files in the same directory
    subtitle_files = _find_subtitle_files(video_path, language)

    if not subtitle_files:
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

    # If language is specified, prioritize matching files
    if language:
        lang_lower = language.lower()
        # Sort files to put language-matching ones first
        files.sort(key=lambda f: (lang_lower not in f.name.lower(), f.name))

    return files


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
