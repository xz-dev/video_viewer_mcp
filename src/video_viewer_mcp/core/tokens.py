"""Token management for YouTube and Bilibili authentication."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ..config import get_data_dir


def _get_tokens_dir() -> Path:
    """Get the tokens directory."""
    tokens_dir = get_data_dir() / "tokens"
    tokens_dir.mkdir(parents=True, exist_ok=True)
    return tokens_dir


def _get_youtube_token_file() -> Path:
    """Get the YouTube token file path."""
    return _get_tokens_dir() / "youtube.json"


def _get_bilibili_token_file() -> Path:
    """Get the Bilibili token file path."""
    return _get_tokens_dir() / "bilibili.json"


# YouTube Token Management


def set_youtube_token(cookies: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Set YouTube cookies for authenticated downloads.

    Args:
        cookies: List of cookie dicts in yt-dlp format
                 Each cookie should have: name, value, domain, path, etc.

    Returns:
        dict with success status
    """
    if not cookies:
        return {
            "success": False,
            "error": "Cookies list cannot be empty",
        }

    token_data = {
        "cookies": cookies,
        "updated_at": datetime.now().isoformat(),
    }

    token_file = _get_youtube_token_file()
    with open(token_file, "w") as f:
        json.dump(token_data, f, indent=2)

    return {
        "success": True,
        "message": f"YouTube token saved with {len(cookies)} cookies",
        "updated_at": token_data["updated_at"],
    }


def get_youtube_token() -> dict[str, Any]:
    """
    Get YouTube token status and cookies.

    Returns:
        dict with token info (cookies included for internal use)
    """
    token_file = _get_youtube_token_file()
    if not token_file.exists():
        return {
            "success": True,
            "exists": False,
            "cookies": None,
        }

    with open(token_file) as f:
        data = json.load(f)

    return {
        "success": True,
        "exists": True,
        "cookies": data.get("cookies"),
        "cookie_count": len(data.get("cookies", [])),
        "updated_at": data.get("updated_at"),
    }


def get_youtube_token_status() -> dict[str, Any]:
    """
    Get YouTube token status (without sensitive data).

    Returns:
        dict with token status (no cookies)
    """
    token = get_youtube_token()
    if not token.get("exists"):
        return {
            "success": True,
            "exists": False,
        }

    return {
        "success": True,
        "exists": True,
        "cookie_count": token.get("cookie_count", 0),
        "updated_at": token.get("updated_at"),
    }


def delete_youtube_token() -> dict[str, Any]:
    """
    Delete YouTube token.

    Returns:
        dict with success status
    """
    token_file = _get_youtube_token_file()
    if token_file.exists():
        token_file.unlink()
        return {
            "success": True,
            "message": "YouTube token deleted",
        }

    return {
        "success": True,
        "message": "YouTube token not found (already deleted)",
    }


# Bilibili Token Management


def set_bilibili_token(
    sessdata: str | None = None,
    access_key: str | None = None,
) -> dict[str, Any]:
    """
    Set Bilibili token (SESSDATA and/or access_key).

    Args:
        sessdata: SESSDATA cookie value for web authentication
        access_key: Access key for APP API authentication

    Returns:
        dict with success status
    """
    if not sessdata and not access_key:
        return {
            "success": False,
            "error": "At least one of sessdata or access_key must be provided",
        }

    # Load existing token to merge
    existing = get_bilibili_token()
    token_data: dict[str, Any] = {
        "updated_at": datetime.now().isoformat(),
    }

    # Update or keep existing values
    if sessdata is not None:
        token_data["sessdata"] = sessdata
    elif existing.get("sessdata"):
        token_data["sessdata"] = existing["sessdata"]

    if access_key is not None:
        token_data["access_key"] = access_key
    elif existing.get("access_key"):
        token_data["access_key"] = existing["access_key"]

    token_file = _get_bilibili_token_file()
    with open(token_file, "w") as f:
        json.dump(token_data, f, indent=2)

    return {
        "success": True,
        "message": "Bilibili token saved",
        "has_sessdata": "sessdata" in token_data,
        "has_access_key": "access_key" in token_data,
        "updated_at": token_data["updated_at"],
    }


def get_bilibili_token() -> dict[str, Any]:
    """
    Get Bilibili token (with sensitive data for internal use).

    Returns:
        dict with token info
    """
    token_file = _get_bilibili_token_file()
    if not token_file.exists():
        return {
            "success": True,
            "exists": False,
            "sessdata": None,
            "access_key": None,
        }

    with open(token_file) as f:
        data = json.load(f)

    return {
        "success": True,
        "exists": True,
        "sessdata": data.get("sessdata"),
        "access_key": data.get("access_key"),
        "updated_at": data.get("updated_at"),
    }


def get_bilibili_token_status() -> dict[str, Any]:
    """
    Get Bilibili token status (without sensitive data).

    Returns:
        dict with token status
    """
    token = get_bilibili_token()
    if not token.get("exists"):
        return {
            "success": True,
            "exists": False,
        }

    return {
        "success": True,
        "exists": True,
        "has_sessdata": token.get("sessdata") is not None,
        "has_access_key": token.get("access_key") is not None,
        "updated_at": token.get("updated_at"),
    }


def delete_bilibili_token() -> dict[str, Any]:
    """
    Delete Bilibili token.

    Returns:
        dict with success status
    """
    token_file = _get_bilibili_token_file()
    if token_file.exists():
        token_file.unlink()
        return {
            "success": True,
            "message": "Bilibili token deleted",
        }

    return {
        "success": True,
        "message": "Bilibili token not found (already deleted)",
    }
