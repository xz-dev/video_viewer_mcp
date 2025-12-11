"""Danmaku (bullet comments) reading from downloaded Bilibili videos."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .download import get_video_path


# Danmaku mode mapping
DANMAKU_MODES = {
    1: "scroll",      # 滚动弹幕
    2: "scroll",      # 滚动弹幕
    3: "scroll",      # 滚动弹幕
    4: "bottom",      # 底部弹幕
    5: "top",         # 顶部弹幕
    6: "reverse",     # 逆向弹幕
    7: "special",     # 特殊弹幕
    8: "code",        # 代码弹幕
}


def get_danmaku(
    url: str,
    start_time: float | None = None,
    end_time: float | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    """
    Get danmaku (bullet comments) for a Bilibili video with pagination.

    Args:
        url: Video URL
        start_time: Filter start time in seconds (optional)
        end_time: Filter end time in seconds (optional)
        page: Page number (1-indexed, default 1)
        page_size: Number of items per page (default 100)

    Returns:
        dict with danmaku entries and pagination info
    """
    # Get the local video path
    video_path = get_video_path(url)
    if not video_path:
        return {
            "success": False,
            "error": "Video not downloaded. Use download_video first.",
        }

    # Find danmaku XML file
    danmaku_file = _find_danmaku_file(video_path)
    if not danmaku_file:
        return {
            "success": False,
            "error": "No danmaku file found. The video may not have danmaku.",
        }

    try:
        entries = _parse_danmaku_xml(danmaku_file)

        # Filter by time range if specified
        if start_time is not None or end_time is not None:
            entries = _filter_by_time(entries, start_time, end_time)

        # Pagination
        total_count = len(entries)
        total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 1
        page = max(1, min(page, total_pages)) if total_pages > 0 else 1

        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_entries = entries[start_idx:end_idx]

        return {
            "success": True,
            "file": str(danmaku_file),
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "count": len(paginated_entries),
            "entries": paginated_entries,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to parse danmaku file: {e}",
        }


def _find_danmaku_file(video_path: Path) -> Path | None:
    """Find danmaku XML file for a video."""
    parent = video_path.parent

    # Look for XML files (BBDown saves danmaku as video.xml)
    xml_files = list(parent.glob("*.xml"))

    if not xml_files:
        return None

    # Return the first XML file found
    return xml_files[0]


def _parse_danmaku_xml(path: Path) -> list[dict[str, Any]]:
    """
    Parse Bilibili danmaku XML format.

    XML format:
    <d p="time,mode,size,color,timestamp,pool,uid_crc32,row_id">content</d>

    Where:
    - time: appearance time in seconds
    - mode: 1-3=scroll, 4=bottom, 5=top, 6=reverse, 7=special, 8=code
    - size: font size (25=normal)
    - color: decimal color value
    - timestamp: send timestamp
    - pool: danmaku pool (0=normal, 1=subtitle, 2=special)
    - uid_crc32: user id hash
    - row_id: danmaku id
    """
    entries = []

    tree = ET.parse(path)
    root = tree.getroot()

    for d_elem in root.findall(".//d"):
        p_attr = d_elem.get("p", "")
        text = d_elem.text or ""

        if not p_attr or not text:
            continue

        parts = p_attr.split(",")
        if len(parts) < 4:
            continue

        try:
            time_sec = float(parts[0])
            mode = int(parts[1])
            color_dec = int(parts[3])

            # Convert decimal color to hex
            color_hex = f"#{color_dec:06X}"

            entries.append({
                "time": time_sec,
                "text": text.strip(),
                "type": DANMAKU_MODES.get(mode, "scroll"),
                "color": color_hex,
            })
        except (ValueError, IndexError):
            continue

    # Sort by time
    entries.sort(key=lambda x: x["time"])

    return entries


def _filter_by_time(
    entries: list[dict[str, Any]],
    start_time: float | None,
    end_time: float | None,
) -> list[dict[str, Any]]:
    """Filter danmaku entries by time range."""
    result = []
    for entry in entries:
        time = entry["time"]
        if start_time is not None and time < start_time:
            continue
        if end_time is not None and time > end_time:
            continue
        result.append(entry)
    return result
