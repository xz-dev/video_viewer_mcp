"""Integration tests for video-viewer-mcp.

Tests both HTTP API and MCP client against a real YouTube video.
Uses the classic "Me at the zoo" - the first YouTube video ever uploaded.
"""

from __future__ import annotations

import asyncio
import base64
import time
from multiprocessing import Process

import httpx
import pytest

# Test video: "Me at the zoo" - first YouTube video
TEST_VIDEO_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
# Test video for Bilibili
TEST_BILIBILI_URL = "https://www.bilibili.com/video/av7/"
BASE_URL = "http://localhost:8765"


def run_server():
    """Run the server in a subprocess."""
    import uvicorn
    from video_viewer_mcp.app import app

    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")


@pytest.fixture(scope="module")
def server():
    """Start the server for testing."""
    proc = Process(target=run_server, daemon=True)
    proc.start()

    # Wait for server to start
    for _ in range(30):
        try:
            httpx.get(f"{BASE_URL}/", timeout=1)
            break
        except httpx.ConnectError:
            time.sleep(0.5)
    else:
        proc.terminate()
        raise RuntimeError("Server failed to start")

    yield proc

    proc.terminate()
    proc.join(timeout=5)


@pytest.fixture(scope="module")
def client(server):
    """HTTP client for testing."""
    with httpx.Client(base_url=BASE_URL, timeout=300) as client:
        yield client


class TestHTTPAPI:
    """Test HTTP REST API endpoints."""

    def test_health_endpoint(self, client: httpx.Client):
        """Test health endpoint returns service info."""
        response = client.get("/api/health")
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == "video-viewer-mcp"
        assert data["status"] == "healthy"
        assert "endpoints" in data
        assert "/api" in data["endpoints"]["api"]

    def test_list_downloads_empty(self, client: httpx.Client):
        """Test listing downloads when empty."""
        response = client.get("/api/downloads")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "jobs" in data

    def test_download_video(self, client: httpx.Client):
        """Test downloading the classic YouTube video."""
        response = client.post(
            "/api/download",
            params={"url": TEST_VIDEO_URL},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "job_id" in data
        assert data["status"] in ("completed", "downloading")

        # Store job_id for later tests
        TestHTTPAPI.job_id = data["job_id"]

    def test_get_download_status(self, client: httpx.Client):
        """Test getting download status."""
        job_id = getattr(TestHTTPAPI, "job_id", None)
        if not job_id:
            pytest.skip("No job_id from previous test")

        response = client.get(f"/api/download/{job_id}")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert data["status"] == "completed"

    def test_list_downloads_with_job(self, client: httpx.Client):
        """Test listing downloads shows our job."""
        response = client.get("/api/downloads")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["count"] >= 1

        job_ids = [job["job_id"] for job in data["jobs"]]
        assert TestHTTPAPI.job_id in job_ids

    def test_get_subtitles(self, client: httpx.Client):
        """Test getting subtitles for downloaded video."""
        response = client.get(
            "/api/subtitles",
            params={"url": TEST_VIDEO_URL},
        )
        assert response.status_code == 200

        data = response.json()
        # Note: This video may or may not have subtitles
        if data.get("success"):
            assert "entries" in data
        else:
            # It's okay if no subtitles exist
            assert "error" in data

    def test_screenshot(self, client: httpx.Client):
        """Test taking a screenshot from the video."""
        response = client.get(
            "/api/screenshot",
            params={
                "url": TEST_VIDEO_URL,
                "timestamp": "5",  # 5 seconds into the video
                "width": 640,
            },
        )
        assert response.status_code == 200

        # Should return PNG image
        assert response.headers.get("content-type") == "image/png"
        assert len(response.content) > 1000  # Should have some image data

    def test_screenshot_different_timestamp(self, client: httpx.Client):
        """Test screenshot at different timestamp."""
        response = client.get(
            "/api/screenshot",
            params={
                "url": TEST_VIDEO_URL,
                "timestamp": "0:00:10",  # 10 seconds, HH:MM:SS format
                "width": 320,
            },
        )
        assert response.status_code == 200
        assert response.headers.get("content-type") == "image/png"


class TestBilibili:
    """Test Bilibili video download via BBDown."""

    def test_download_bilibili_video(self, client: httpx.Client):
        """Test downloading a Bilibili video via BBDown."""
        response = client.post(
            "/api/download",
            params={"url": TEST_BILIBILI_URL},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "job_id" in data
        assert data["status"] in ("completed", "downloading")

        # Store job_id for later tests
        TestBilibili.job_id = data["job_id"]

    def test_get_bilibili_download_status(self, client: httpx.Client):
        """Test getting Bilibili download status."""
        job_id = getattr(TestBilibili, "job_id", None)
        if not job_id:
            pytest.skip("No job_id from previous test")

        response = client.get(f"/api/download/{job_id}")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert data["status"] == "completed"

    def test_bilibili_screenshot(self, client: httpx.Client):
        """Test taking a screenshot from the Bilibili video."""
        response = client.get(
            "/api/screenshot",
            params={
                "url": TEST_BILIBILI_URL,
                "timestamp": "0",  # Start of video
                "width": 640,
            },
        )
        assert response.status_code == 200

        # Should return PNG image
        assert response.headers.get("content-type") == "image/png"
        assert len(response.content) > 100  # Should have some image data (may be small for short videos)


class TestTokens:
    """Test token management API endpoints."""

    def test_youtube_token_not_exists(self, client: httpx.Client):
        """Test getting YouTube token when not set."""
        response = client.get("/api/tokens/youtube")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["exists"] is False

    def test_set_youtube_token(self, client: httpx.Client):
        """Test setting YouTube cookies."""
        response = client.post(
            "/api/tokens/youtube",
            json={
                "cookies": [
                    {"name": "TEST_COOKIE", "value": "test_value", "domain": ".youtube.com"}
                ]
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "YouTube token saved" in data["message"]

    def test_get_youtube_token_exists(self, client: httpx.Client):
        """Test getting YouTube token after setting."""
        response = client.get("/api/tokens/youtube")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["exists"] is True
        assert data["cookie_count"] == 1

    def test_delete_youtube_token(self, client: httpx.Client):
        """Test deleting YouTube token."""
        response = client.delete("/api/tokens/youtube")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True

        # Verify deleted
        response = client.get("/api/tokens/youtube")
        data = response.json()
        assert data["exists"] is False

    def test_bilibili_token_not_exists(self, client: httpx.Client):
        """Test getting Bilibili token when not set."""
        response = client.get("/api/tokens/bilibili")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["exists"] is False

    def test_set_bilibili_token(self, client: httpx.Client):
        """Test setting Bilibili token."""
        response = client.post(
            "/api/tokens/bilibili",
            json={
                "sessdata": "test_sessdata_value",
                "access_key": "test_access_key_value",
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["has_sessdata"] is True
        assert data["has_access_key"] is True

    def test_get_bilibili_token_exists(self, client: httpx.Client):
        """Test getting Bilibili token after setting."""
        response = client.get("/api/tokens/bilibili")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["exists"] is True
        assert data["has_sessdata"] is True
        assert data["has_access_key"] is True

    def test_delete_bilibili_token(self, client: httpx.Client):
        """Test deleting Bilibili token."""
        response = client.delete("/api/tokens/bilibili")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True

        # Verify deleted
        response = client.get("/api/tokens/bilibili")
        data = response.json()
        assert data["exists"] is False


class TestMCPClient:
    """Test MCP client functionality via streamable HTTP transport."""

    @pytest.fixture
    def mcp_client(self, server):
        """Create MCP client."""
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        return streamablehttp_client, ClientSession

    @pytest.mark.asyncio
    async def test_mcp_list_tools(self, mcp_client):
        """Test listing available MCP tools."""
        streamablehttp_client, ClientSession = mcp_client

        async with streamablehttp_client(f"{BASE_URL}/mcp") as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools = await session.list_tools()
                tool_names = [t.name for t in tools.tools]

                assert "tool_download_video" in tool_names
                assert "tool_get_download_status" in tool_names
                assert "tool_list_downloads" in tool_names
                assert "tool_get_subtitles" in tool_names
                assert "tool_screenshot" in tool_names
                # Token management tools
                assert "tool_set_youtube_token" in tool_names
                assert "tool_get_youtube_token" in tool_names
                assert "tool_delete_youtube_token" in tool_names
                assert "tool_set_bilibili_token" in tool_names
                assert "tool_get_bilibili_token" in tool_names
                assert "tool_delete_bilibili_token" in tool_names

    @pytest.mark.asyncio
    async def test_mcp_download_video(self, mcp_client):
        """Test downloading video via MCP."""
        streamablehttp_client, ClientSession = mcp_client

        async with streamablehttp_client(f"{BASE_URL}/mcp") as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()

                result = await session.call_tool(
                    "tool_download_video",
                    arguments={"url": TEST_VIDEO_URL},
                )

                # Parse the result
                assert len(result.content) > 0
                content = result.content[0]
                assert content.type == "text"

                import json
                data = json.loads(content.text)
                assert data["success"] is True
                assert "job_id" in data

                TestMCPClient.job_id = data["job_id"]

    @pytest.mark.asyncio
    async def test_mcp_list_downloads(self, mcp_client):
        """Test listing downloads via MCP."""
        streamablehttp_client, ClientSession = mcp_client

        async with streamablehttp_client(f"{BASE_URL}/mcp") as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()

                result = await session.call_tool(
                    "tool_list_downloads",
                    arguments={},
                )

                content = result.content[0]
                import json
                data = json.loads(content.text)
                assert data["success"] is True
                assert data["count"] >= 1

    @pytest.mark.asyncio
    async def test_mcp_get_subtitles(self, mcp_client):
        """Test getting subtitles via MCP."""
        streamablehttp_client, ClientSession = mcp_client

        async with streamablehttp_client(f"{BASE_URL}/mcp") as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()

                result = await session.call_tool(
                    "tool_get_subtitles",
                    arguments={"url": TEST_VIDEO_URL},
                )

                content = result.content[0]
                import json
                data = json.loads(content.text)
                # May or may not have subtitles
                assert "success" in data or "error" in data

    @pytest.mark.asyncio
    async def test_mcp_screenshot(self, mcp_client):
        """Test screenshot via MCP."""
        streamablehttp_client, ClientSession = mcp_client

        async with streamablehttp_client(f"{BASE_URL}/mcp") as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()

                result = await session.call_tool(
                    "tool_screenshot",
                    arguments={
                        "url": TEST_VIDEO_URL,
                        "timestamp": "5",
                        "width": 640,
                    },
                )

                content = result.content[0]
                # Should return ImageContent, not TextContent
                assert content.type == "image"
                assert content.mimeType == "image/png"
                # Verify it's valid base64
                base64.b64decode(content.data)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
