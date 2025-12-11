"""FastAPI application for video-viewer-mcp."""

from __future__ import annotations

from fastapi import FastAPI

from .api import router as api_router
from .config import ensure_dirs
from .server import mcp

# Create FastAPI app
app = FastAPI(
    title="Video Viewer MCP",
    description="MCP server for video viewing - download, subtitles, screenshots",
    version="0.1.0",
)

# Include REST API routes
app.include_router(api_router, prefix="/api", tags=["API"])

# Mount MCP server routes
# sse_app provides /sse and /messages endpoints
# streamable_http_app provides /mcp endpoint
# Mount at root so paths stay as /sse, /mcp, /messages
app.mount("/", mcp.sse_app())
app.mount("/", mcp.streamable_http_app())


@app.on_event("startup")
async def startup():
    """Initialize on startup."""
    ensure_dirs()


def main():
    """Run the server."""
    import uvicorn

    uvicorn.run(
        "video_viewer_mcp.app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()
