"""Basic settings and directory management."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from platformdirs import user_config_dir, user_data_dir


def get_config_dir() -> Path:
    """Get the configuration directory."""
    return Path(os.environ.get("VIDEO_MCP_CONFIG_DIR", user_config_dir("video-viewer-mcp")))


def get_data_dir() -> Path:
    """Get the data directory for storing job status files."""
    return Path(os.environ.get("VIDEO_MCP_DATA_DIR", user_data_dir("video-viewer-mcp")))


def get_download_dir() -> Path:
    """Get the default download directory."""
    default = Path.home() / "Videos" / "video-viewer-mcp"
    return Path(os.environ.get("VIDEO_MCP_DOWNLOAD_DIR", str(default)))


def get_config_file() -> Path:
    """Get the config file path."""
    return get_config_dir() / "config.json"


def load_config() -> dict[str, Any]:
    """Load configuration from file."""
    config: dict[str, Any] = {}
    config_file = get_config_file()
    if config_file.exists():
        with open(config_file) as f:
            config = json.load(f)
    return config


def save_config(config: dict[str, Any]) -> None:
    """Save configuration to file."""
    config_file = get_config_file()
    config_file.parent.mkdir(parents=True, exist_ok=True)
    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)


def get_tokens_dir() -> Path:
    """Get the tokens directory for storing authentication tokens."""
    return get_data_dir() / "tokens"


def ensure_dirs() -> None:
    """Ensure all required directories exist."""
    get_config_dir().mkdir(parents=True, exist_ok=True)
    get_data_dir().mkdir(parents=True, exist_ok=True)
    get_download_dir().mkdir(parents=True, exist_ok=True)
    get_tokens_dir().mkdir(parents=True, exist_ok=True)
    (get_data_dir() / "jobs").mkdir(parents=True, exist_ok=True)


# Cleanup configuration
DEFAULT_CLEANUP_CONFIG = {
    "enabled": True,
    "retention_days": 4 / 24,  # 4 hours
    "schedule": "0 */6 * * *",  # Every 6 hours
}


def get_cleanup_config() -> dict[str, Any]:
    """Get cleanup configuration with defaults."""
    config = load_config()
    cleanup = config.get("cleanup", {})
    return {**DEFAULT_CLEANUP_CONFIG, **cleanup}
