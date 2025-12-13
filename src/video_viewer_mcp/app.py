"""FastAPI application for video-viewer-mcp."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api import router as api_router
from .config import ensure_dirs
from .core.scheduler import CleanupScheduler
from .server import mcp

# Create global cleanup scheduler instance
cleanup_scheduler = CleanupScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    ensure_dirs()

    # Start cleanup scheduler
    await cleanup_scheduler.start()

    # Initialize MCP session manager (required for streamable HTTP)
    # This triggers mcp.streamable_http_app() to create session_manager
    mcp_app = mcp.streamable_http_app()
    async with mcp.session_manager.run():
        yield

    # Stop cleanup scheduler
    await cleanup_scheduler.stop()


# Create FastAPI app with lifespan
app = FastAPI(
    title="Video Viewer MCP",
    description="MCP server for video viewing - download, subtitles, screenshots",
    version="0.1.0",
    lifespan=lifespan,
)

# Include REST API routes
app.include_router(api_router, prefix="/api", tags=["API"])

# Mount MCP server routes (streamable HTTP only, provides /mcp endpoint)
app.mount("/", mcp.streamable_http_app())


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
