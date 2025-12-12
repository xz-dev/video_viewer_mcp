"""Tests for screenshot and resolution features."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from video_viewer_mcp.core.screenshot import get_video_resolution, capture_screenshot


class TestGetVideoResolution:
    """Test get_video_resolution function."""

    def test_nonexistent_file_returns_none(self):
        """Test that non-existent file returns (None, None)."""
        width, height = get_video_resolution("/nonexistent/video.mp4")
        assert width is None
        assert height is None

    def test_invalid_file_returns_none(self, tmp_path: Path):
        """Test that invalid file returns (None, None)."""
        # Create a fake file that's not a video
        fake_video = tmp_path / "fake.mp4"
        fake_video.write_text("not a video")

        width, height = get_video_resolution(fake_video)
        assert width is None
        assert height is None

    def test_valid_video_returns_resolution(self):
        """Test that valid video returns resolution."""
        # Mock av.open to return a video with known resolution
        mock_stream = MagicMock()
        mock_stream.width = 1920
        mock_stream.height = 1080

        mock_container = MagicMock()
        mock_container.streams.video = [mock_stream]
        mock_container.__enter__ = MagicMock(return_value=mock_container)
        mock_container.__exit__ = MagicMock(return_value=False)

        with patch("video_viewer_mcp.core.screenshot.av.open", return_value=mock_container):
            with tempfile.NamedTemporaryFile(suffix=".mp4") as f:
                width, height = get_video_resolution(f.name)

        assert width == 1920
        assert height == 1080


class TestAutoScaling:
    """Test auto-scaling logic in screenshot functions."""

    def test_auto_scale_large_landscape_video(self):
        """Test that landscape videos with max dimension > 1280px get width scaled to 1280."""
        # Mock metadata with 1080p video (landscape)
        mock_metadata = {"width": 1920, "height": 1080}

        with patch("video_viewer_mcp.server.get_video_metadata", return_value=mock_metadata):
            with patch("video_viewer_mcp.server.get_video_path", return_value=Path("/fake/video.mp4")):
                with patch("video_viewer_mcp.server.capture_screenshot") as mock_capture:
                    mock_capture.return_value = (b"fake_image", "image/png")

                    from video_viewer_mcp.server import tool_screenshot

                    # Call without width - should auto-scale
                    result = tool_screenshot(
                        url="https://example.com/video",
                        timestamp="10",
                        width=None,
                        height=None,
                    )

                    # Verify capture_screenshot was called with width=1280
                    mock_capture.assert_called_once()
                    call_args = mock_capture.call_args
                    assert call_args[0][2] == 1280  # width argument

    def test_auto_scale_large_portrait_video(self):
        """Test that portrait videos with max dimension > 1280px get height scaled to 1280."""
        # Mock metadata with portrait video (9:16 aspect ratio)
        mock_metadata = {"width": 1080, "height": 1920}

        with patch("video_viewer_mcp.server.get_video_metadata", return_value=mock_metadata):
            with patch("video_viewer_mcp.server.get_video_path", return_value=Path("/fake/video.mp4")):
                with patch("video_viewer_mcp.server.capture_screenshot") as mock_capture:
                    mock_capture.return_value = (b"fake_image", "image/png")

                    from video_viewer_mcp.server import tool_screenshot

                    # Call without dimensions - should auto-scale height
                    result = tool_screenshot(
                        url="https://example.com/video",
                        timestamp="10",
                        width=None,
                        height=None,
                    )

                    # Verify capture_screenshot was called with height=1280
                    mock_capture.assert_called_once()
                    call_args = mock_capture.call_args
                    assert call_args[0][2] is None  # width argument
                    assert call_args[0][3] == 1280  # height argument

    def test_no_scale_small_video(self):
        """Test that videos with max dimension <= 1280px are not scaled."""
        # Mock metadata with 720p video
        mock_metadata = {"width": 1280, "height": 720}

        with patch("video_viewer_mcp.server.get_video_metadata", return_value=mock_metadata):
            with patch("video_viewer_mcp.server.get_video_path", return_value=Path("/fake/video.mp4")):
                with patch("video_viewer_mcp.server.capture_screenshot") as mock_capture:
                    mock_capture.return_value = (b"fake_image", "image/png")

                    from video_viewer_mcp.server import tool_screenshot

                    # Call without width - should keep original
                    result = tool_screenshot(
                        url="https://example.com/video",
                        timestamp="10",
                        width=None,
                        height=None,
                    )

                    # Verify capture_screenshot was called with width=None
                    mock_capture.assert_called_once()
                    call_args = mock_capture.call_args
                    assert call_args[0][2] is None  # width argument

    def test_explicit_width_overrides_auto_scale(self):
        """Test that explicit width parameter overrides auto-scaling."""
        # Mock metadata with 4K video
        mock_metadata = {"width": 3840, "height": 2160}

        with patch("video_viewer_mcp.server.get_video_metadata", return_value=mock_metadata):
            with patch("video_viewer_mcp.server.get_video_path", return_value=Path("/fake/video.mp4")):
                with patch("video_viewer_mcp.server.capture_screenshot") as mock_capture:
                    mock_capture.return_value = (b"fake_image", "image/png")

                    from video_viewer_mcp.server import tool_screenshot

                    # Call with explicit width=640
                    result = tool_screenshot(
                        url="https://example.com/video",
                        timestamp="10",
                        width=640,
                        height=None,
                    )

                    # Verify capture_screenshot was called with width=640
                    mock_capture.assert_called_once()
                    call_args = mock_capture.call_args
                    assert call_args[0][2] == 640  # width argument

    def test_no_metadata_no_scaling(self):
        """Test that missing metadata results in no scaling."""
        with patch("video_viewer_mcp.server.get_video_metadata", return_value=None):
            with patch("video_viewer_mcp.server.get_video_path", return_value=Path("/fake/video.mp4")):
                with patch("video_viewer_mcp.server.capture_screenshot") as mock_capture:
                    mock_capture.return_value = (b"fake_image", "image/png")

                    from video_viewer_mcp.server import tool_screenshot

                    # Call without width - should not scale (no metadata)
                    result = tool_screenshot(
                        url="https://example.com/video",
                        timestamp="10",
                        width=None,
                        height=None,
                    )

                    # Verify capture_screenshot was called with width=None
                    mock_capture.assert_called_once()
                    call_args = mock_capture.call_args
                    assert call_args[0][2] is None  # width argument

    def test_metadata_without_width(self):
        """Test that metadata without width field results in no scaling."""
        mock_metadata = {"title": "Test Video", "duration": 120}

        with patch("video_viewer_mcp.server.get_video_metadata", return_value=mock_metadata):
            with patch("video_viewer_mcp.server.get_video_path", return_value=Path("/fake/video.mp4")):
                with patch("video_viewer_mcp.server.capture_screenshot") as mock_capture:
                    mock_capture.return_value = (b"fake_image", "image/png")

                    from video_viewer_mcp.server import tool_screenshot

                    # Call without width - should not scale (no width in metadata)
                    result = tool_screenshot(
                        url="https://example.com/video",
                        timestamp="10",
                        width=None,
                        height=None,
                    )

                    # Verify capture_screenshot was called with width=None
                    mock_capture.assert_called_once()
                    call_args = mock_capture.call_args
                    assert call_args[0][2] is None  # width argument


class TestMetadataResolution:
    """Test that metadata includes resolution fields."""

    def test_ytdlp_metadata_includes_resolution(self):
        """Test that yt-dlp downloader includes width/height in metadata."""
        import yt_dlp

        mock_info = {
            "title": "Test Video",
            "duration": 120,
            "uploader": "Test User",
            "width": 1920,
            "height": 1080,
        }

        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = mock_info
        mock_ydl.prepare_filename.return_value = "/tmp/test/video.mp4"
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)

        with patch.object(yt_dlp, "YoutubeDL", return_value=mock_ydl):
            with patch("video_viewer_mcp.config.downloaders._get_youtube_cookies", return_value=None):
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmpdir = Path(tmpdir)
                    from video_viewer_mcp.config.downloaders import _download_with_ytdlp

                    result = _download_with_ytdlp(
                        url="https://youtube.com/watch?v=test",
                        output_dir=tmpdir,
                        job_id="test_job_123",
                        progress_callback=None,
                    )

                    # Check info.json was written with resolution
                    info_path = tmpdir / "info.json"
                    assert info_path.exists()

                    with open(info_path) as f:
                        saved_info = json.load(f)

                    assert saved_info["width"] == 1920
                    assert saved_info["height"] == 1080


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
