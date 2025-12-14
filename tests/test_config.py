"""Tests for cleanup configuration."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from video_viewer_mcp.config.settings import get_cleanup_config


def test_get_cleanup_config_defaults():
    """Test default configuration is returned when no config file exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "config.json"

        # Mock load_config to return empty dict
        with patch("video_viewer_mcp.config.settings.load_config", return_value={}):
            config = get_cleanup_config()

            # Verify defaults (4 hours retention, every 6 hours)
            assert config["enabled"] is True
            assert config["retention_days"] == 4 / 24  # 4 hours
            assert config["schedule"] == "0 */6 * * *"  # Every 6 hours


def test_get_cleanup_config_custom():
    """Test custom configuration overrides defaults."""
    custom_config = {"cleanup": {"enabled": False, "retention_days": 7, "schedule": "0 3 * * *"}}

    with patch("video_viewer_mcp.config.settings.load_config", return_value=custom_config):
        config = get_cleanup_config()

        # Verify custom values
        assert config["enabled"] is False
        assert config["retention_days"] == 7
        assert config["schedule"] == "0 3 * * *"


def test_get_cleanup_config_partial_custom():
    """Test partial custom configuration merges with defaults."""
    # Only override retention_days
    partial_config = {"cleanup": {"retention_days": 3}}

    with patch("video_viewer_mcp.config.settings.load_config", return_value=partial_config):
        config = get_cleanup_config()

        # Custom value
        assert config["retention_days"] == 3

        # Defaults for others
        assert config["enabled"] is True
        assert config["schedule"] == "0 */6 * * *"  # Default: every 6 hours


def test_get_cleanup_config_fractional_retention():
    """Test fractional retention days (e.g., 0.5 for 12 hours)."""
    fractional_config = {"cleanup": {"retention_days": 0.5}}

    with patch("video_viewer_mcp.config.settings.load_config", return_value=fractional_config):
        config = get_cleanup_config()

        assert config["retention_days"] == 0.5


def test_get_cleanup_config_different_schedule():
    """Test different schedule formats."""
    # Test hourly schedule
    hourly_config = {"cleanup": {"schedule": "0 * * * *"}}

    with patch("video_viewer_mcp.config.settings.load_config", return_value=hourly_config):
        config = get_cleanup_config()

        assert config["schedule"] == "0 * * * *"

    # Test every 5 minutes schedule
    frequent_config = {"cleanup": {"schedule": "*/5 * * * *"}}

    with patch("video_viewer_mcp.config.settings.load_config", return_value=frequent_config):
        config = get_cleanup_config()

        assert config["schedule"] == "*/5 * * * *"
