"""Tests for metadata query functionality."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from video_viewer_mcp.core.metadata import (
    query_video_info,
    _extract_default_fields,
    _extract_fields_by_path,
    DEFAULT_METADATA_FIELDS,
)


class TestExtractDefaultFields:
    """Test _extract_default_fields function."""

    def test_extracts_only_default_fields(self):
        """Test that only DEFAULT_METADATA_FIELDS are extracted."""
        full_info = {
            "id": "test123",
            "title": "Test Video",
            "description": "A test video",
            "duration": 123,
            "formats": [{"format_id": "18"}],  # Not in default fields
            "thumbnails": [{"url": "http://example.com"}],  # Not in default fields
            "protocol": "https",  # Not in default fields
        }

        result = _extract_default_fields(full_info)

        assert "id" in result
        assert "title" in result
        assert "description" in result
        assert "duration" in result
        assert "formats" not in result
        assert "thumbnails" not in result
        assert "protocol" not in result

    def test_skips_none_values(self):
        """Test that None values are not included."""
        full_info = {
            "id": "test123",
            "title": "Test Video",
            "description": None,
            "duration": None,
        }

        result = _extract_default_fields(full_info)

        assert "id" in result
        assert "title" in result
        assert "description" not in result
        assert "duration" not in result

    def test_all_default_fields_extracted_when_present(self):
        """Test all default fields are extracted when available."""
        full_info = {field: f"value_{field}" for field in DEFAULT_METADATA_FIELDS}

        result = _extract_default_fields(full_info)

        for field in DEFAULT_METADATA_FIELDS:
            assert field in result
            assert result[field] == f"value_{field}"


class TestExtractFieldsByPath:
    """Test _extract_fields_by_path function."""

    def test_top_level_field(self):
        """Test extracting top-level field."""
        info = {
            "formats": [{"format_id": "18", "ext": "mp4"}],
            "thumbnails": [{"url": "http://example.com"}],
        }

        result = _extract_fields_by_path(info, ["formats"])

        assert "formats" in result
        assert result["formats"] == info["formats"]

    def test_dot_notation_list_field(self):
        """Test extracting subfield from list (e.g., formats.resolution)."""
        info = {
            "formats": [
                {"format_id": "18", "resolution": "720p"},
                {"format_id": "22", "resolution": "1080p"},
                {"format_id": "140"},  # No resolution field
            ]
        }

        result = _extract_fields_by_path(info, ["formats.resolution"])

        assert "formats_resolution" in result
        assert result["formats_resolution"] == ["720p", "1080p"]

    def test_dot_notation_dict_field(self):
        """Test extracting subfield from dict (e.g., subtitles.en)."""
        info = {
            "subtitles": {
                "en": [{"url": "http://example.com/en.vtt"}],
                "zh": [{"url": "http://example.com/zh.vtt"}],
            }
        }

        result = _extract_fields_by_path(info, ["subtitles.en"])

        assert "subtitles_en" in result
        assert result["subtitles_en"] == info["subtitles"]["en"]

    def test_multiple_paths(self):
        """Test extracting multiple paths at once."""
        info = {
            "formats": [{"resolution": "720p"}],
            "thumbnails": [{"url": "http://example.com"}],
        }

        result = _extract_fields_by_path(info, ["formats", "thumbnails"])

        assert "formats" in result
        assert "thumbnails" in result

    def test_missing_field_ignored(self):
        """Test that missing fields are silently ignored."""
        info = {"title": "Test"}

        result = _extract_fields_by_path(info, ["formats", "nonexistent"])

        assert "formats" not in result
        assert "nonexistent" not in result

    def test_missing_subfield_ignored(self):
        """Test that missing subfields are silently ignored."""
        info = {"subtitles": {"en": [{"url": "test"}]}}

        result = _extract_fields_by_path(info, ["subtitles.ja"])

        assert "subtitles_ja" not in result


class TestQueryVideoInfo:
    """Test query_video_info function."""

    def test_query_remote_video_returns_default_fields_only(self):
        """Test that remote query returns only default fields."""
        mock_info = {
            "id": "test123",
            "title": "Test Video",
            "duration": 123,
            "width": 1920,
            "height": 1080,
            "uploader": "Test Channel",
            "view_count": 1000000,
            "formats": [{"format_id": "18", "ext": "mp4"}],  # Should not be in result
            "protocol": "https",  # Should not be in result
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
        # These should NOT be in the result (not in DEFAULT_METADATA_FIELDS)
        assert "formats" not in result["data"]
        assert "protocol" not in result["data"]

    def test_query_with_extra_fields(self):
        """Test that extra_fields returns additional data."""
        mock_info = {
            "id": "test123",
            "title": "Test Video",
            "formats": [{"format_id": "18", "resolution": "720p"}],
            "thumbnails": [{"url": "http://example.com"}],
        }

        mock_ydl = MagicMock()
        mock_ydl.__enter__.return_value.extract_info.return_value = mock_info

        with patch("video_viewer_mcp.core.metadata.get_video_dir_by_url", return_value=None):
            with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
                result = query_video_info(
                    "https://www.youtube.com/watch?v=test",
                    extra_fields=["formats", "thumbnails"]
                )

        assert result["success"] is True
        assert "formats" in result["data"]
        assert "thumbnails" in result["data"]

    def test_query_with_extra_fields_dot_notation(self):
        """Test extra_fields with dot notation."""
        mock_info = {
            "id": "test123",
            "title": "Test Video",
            "formats": [
                {"format_id": "18", "resolution": "720p"},
                {"format_id": "22", "resolution": "1080p"},
            ],
        }

        mock_ydl = MagicMock()
        mock_ydl.__enter__.return_value.extract_info.return_value = mock_info

        with patch("video_viewer_mcp.core.metadata.get_video_dir_by_url", return_value=None):
            with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
                result = query_video_info(
                    "https://www.youtube.com/watch?v=test",
                    extra_fields=["formats.resolution"]
                )

        assert result["success"] is True
        assert "formats_resolution" in result["data"]
        assert result["data"]["formats_resolution"] == ["720p", "1080p"]

    def test_query_cached_video_applies_filtering(self):
        """Test that cached metadata is also filtered to default fields."""
        # Simulate full metadata stored on disk
        cached_metadata = {
            "id": "cached123",
            "title": "Cached Video",
            "duration": 456,
            "width": 1280,
            "height": 720,
            "formats": [{"format_id": "18"}],  # Should be filtered out
            "protocol": "https",  # Should be filtered out
            "downloaded_at": "2024-01-01T00:00:00",
        }

        mock_video_dir = Path("/fake/video/dir")

        with patch("video_viewer_mcp.core.metadata.get_video_dir_by_url", return_value=mock_video_dir):
            with patch("video_viewer_mcp.core.metadata._load_metadata", return_value=cached_metadata):
                result = query_video_info("https://www.youtube.com/watch?v=cached")

        assert result["success"] is True
        assert result["cached"] is True
        assert result["data"]["title"] == "Cached Video"
        # These should be filtered out
        assert "formats" not in result["data"]
        assert "protocol" not in result["data"]

    def test_query_cached_video_with_extra_fields(self):
        """Test that extra_fields work with cached metadata."""
        cached_metadata = {
            "id": "cached123",
            "title": "Cached Video",
            "formats": [{"format_id": "18", "resolution": "720p"}],
            "thumbnails": [{"url": "http://example.com"}],
        }

        mock_video_dir = Path("/fake/video/dir")

        with patch("video_viewer_mcp.core.metadata.get_video_dir_by_url", return_value=mock_video_dir):
            with patch("video_viewer_mcp.core.metadata._load_metadata", return_value=cached_metadata):
                result = query_video_info(
                    "https://www.youtube.com/watch?v=cached",
                    extra_fields=["formats", "formats.resolution"]
                )

        assert result["success"] is True
        assert result["cached"] is True
        assert "formats" in result["data"]
        assert "formats_resolution" in result["data"]

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
            "id": "test123",
            "title": "Test Video",
            "duration": 123,
            "description": None,  # Should be excluded
            "uploader": "Test Channel",
            "tags": None,  # Should be excluded
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
