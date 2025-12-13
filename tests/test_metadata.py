"""Tests for metadata query functionality."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from video_viewer_mcp.core.metadata import query_video_info


class TestQueryVideoInfo:
    """Test query_video_info function."""

    def test_query_remote_video_success(self):
        """Test successful remote metadata query."""
        mock_info = {
            "title": "Test Video",
            "duration": 123,
            "width": 1920,
            "height": 1080,
            "uploader": "Test Channel",
            "view_count": 1000000,
            "formats": [{"format_id": "18", "ext": "mp4"}],
        }

        mock_ydl = MagicMock()
        mock_ydl.__enter__.return_value.extract_info.return_value = mock_info

        with patch("video_viewer_mcp.core.metadata.get_video_dir_by_url", return_value=None):
            with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
                result = query_video_info("https://www.youtube.com/watch?v=test")

        assert result["success"] is True
        assert result["cached"] is False
        assert "data" in result
        assert result["data"]["title"] == "Test Video"
        assert result["data"]["duration"] == 123

    def test_query_cached_video(self):
        """Test querying metadata from already-downloaded video."""
        cached_metadata = {
            "title": "Cached Video",
            "duration": 456,
            "width": 1280,
            "height": 720,
        }

        mock_video_dir = Path("/fake/video/dir")

        with patch("video_viewer_mcp.core.metadata.get_video_dir_by_url", return_value=mock_video_dir):
            with patch("video_viewer_mcp.core.metadata._load_metadata", return_value=cached_metadata):
                result = query_video_info("https://www.youtube.com/watch?v=cached")

        assert result["success"] is True
        assert result["cached"] is True
        assert result["data"] == cached_metadata

    def test_query_invalid_url(self):
        """Test handling of invalid URL."""
        mock_ydl = MagicMock()
        mock_ydl.__enter__.return_value.extract_info.side_effect = \
            Exception("DownloadError: Invalid URL")

        with patch("video_viewer_mcp.core.metadata.get_video_dir_by_url", return_value=None):
            with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
                result = query_video_info("https://invalid-url.com/video")

        assert result["success"] is False
        assert "error" in result

    def test_query_no_info_returned(self):
        """Test when yt-dlp returns None."""
        mock_ydl = MagicMock()
        mock_ydl.__enter__.return_value.extract_info.return_value = None

        with patch("video_viewer_mcp.core.metadata.get_video_dir_by_url", return_value=None):
            with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
                result = query_video_info("https://www.youtube.com/watch?v=test")

        assert result["success"] is False
        assert result["error"] == "Could not extract video info from URL"

    def test_query_removes_none_values(self):
        """Test that None values are filtered from response."""
        mock_info = {
            "title": "Test Video",
            "duration": 123,
            "description": None,
            "uploader": "Test Channel",
            "tags": None,
        }

        mock_ydl = MagicMock()
        mock_ydl.__enter__.return_value.extract_info.return_value = mock_info

        with patch("video_viewer_mcp.core.metadata.get_video_dir_by_url", return_value=None):
            with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
                result = query_video_info("https://www.youtube.com/watch?v=test")

        assert result["success"] is True
        assert "description" not in result["data"]
        assert "tags" not in result["data"]
        assert "title" in result["data"]
        assert "uploader" in result["data"]
