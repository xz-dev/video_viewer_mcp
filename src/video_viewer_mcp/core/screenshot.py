"""Screenshot capture using PyAV."""

from __future__ import annotations

import base64
import io
import re
from pathlib import Path

import av
from PIL import Image


def parse_timestamp(timestamp: str) -> float:
    """
    Parse timestamp string to seconds.

    Supported formats:
    - "123.45" (seconds)
    - "1:23.45" (minutes:seconds)
    - "1:23:45.67" (hours:minutes:seconds)
    - "01:23:45,670" (SRT format)

    Returns:
        float: Timestamp in seconds
    """
    timestamp = timestamp.strip()

    # Try parsing as float (seconds)
    try:
        return float(timestamp)
    except ValueError:
        pass

    # Replace comma with dot for SRT format
    timestamp = timestamp.replace(",", ".")

    # Parse HH:MM:SS.mmm or MM:SS.mmm format
    match = re.match(r"(?:(\d+):)?(\d+):(\d+(?:\.\d+)?)", timestamp)
    if match:
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2))
        seconds = float(match.group(3))
        return hours * 3600 + minutes * 60 + seconds

    raise ValueError(f"Invalid timestamp format: {timestamp}")


def capture_screenshot(
    video_path: str | Path,
    timestamp: str | float,
    width: int | None = None,
    height: int | None = None,
    output_format: str = "PNG",
) -> tuple[bytes, str]:
    """
    Capture a frame from video at specified timestamp.

    Args:
        video_path: Path to the video file
        timestamp: Timestamp as seconds (float) or string (HH:MM:SS.mmm)
        width: Optional resize width (maintains aspect ratio if only one dimension)
        height: Optional resize height (maintains aspect ratio if only one dimension)
        output_format: Output format (PNG or JPEG)

    Returns:
        tuple: (image_bytes, mime_type)
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # Parse timestamp if string
    if isinstance(timestamp, str):
        timestamp_sec = parse_timestamp(timestamp)
    else:
        timestamp_sec = float(timestamp)

    container = av.open(str(video_path))

    try:
        stream = container.streams.video[0]

        # Seek to target timestamp
        # av.time_base is 1/1000000 (microseconds)
        target_ts = int(timestamp_sec * av.time_base)
        container.seek(target_ts)

        # Decode the first frame after seeking
        for frame in container.decode(video=0):
            img = frame.to_image()

            # Resize if requested
            if width or height:
                orig_w, orig_h = img.size
                if width and not height:
                    height = int(orig_h * width / orig_w)
                elif height and not width:
                    width = int(orig_w * height / orig_h)
                elif width and height:
                    pass  # Use both dimensions as provided
                img = img.resize((width, height), Image.Resampling.LANCZOS)

            # Convert to bytes
            buffer = io.BytesIO()
            output_format = output_format.upper()
            if output_format == "JPEG":
                img.save(buffer, format="JPEG", quality=95)
                mime_type = "image/jpeg"
            else:
                img.save(buffer, format="PNG")
                mime_type = "image/png"

            return buffer.getvalue(), mime_type

        raise ValueError(f"Could not decode frame at timestamp {timestamp_sec}s")

    finally:
        container.close()


def capture_screenshot_base64(
    video_path: str | Path,
    timestamp: str | float,
    width: int | None = None,
    height: int | None = None,
    output_format: str = "PNG",
) -> tuple[str, str]:
    """
    Capture a frame and return as base64 encoded string.

    Returns:
        tuple: (base64_data, mime_type)
    """
    image_bytes, mime_type = capture_screenshot(
        video_path, timestamp, width, height, output_format
    )
    return base64.b64encode(image_bytes).decode("ascii"), mime_type


def save_screenshot(
    video_path: str | Path,
    timestamp: str | float,
    output_path: str | Path,
    width: int | None = None,
    height: int | None = None,
) -> Path:
    """
    Capture a frame and save to file.

    Returns:
        Path: The output file path
    """
    output_path = Path(output_path)
    output_format = "JPEG" if output_path.suffix.lower() in (".jpg", ".jpeg") else "PNG"

    image_bytes, _ = capture_screenshot(
        video_path, timestamp, width, height, output_format
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(image_bytes)

    return output_path
