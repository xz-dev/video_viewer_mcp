# Video Viewer MCP

MCP server for video viewing - download videos, extract subtitles, and capture screenshots.

## Features

- **Video Download**: Download videos from YouTube, Bilibili, and other platforms supported by yt-dlp
- **Subtitles Extraction**: Get subtitles/captions from downloaded videos
- **Screenshot Capture**: Capture frames at specific timestamps
- **Authentication Support**: YouTube cookies and Bilibili tokens for members-only content

## Installation

### Using uv (Recommended)

```bash
uv sync
uv run video-viewer-mcp
```

### Using pip

```bash
pip install -e .
video-viewer-mcp
```

### Using Container

From GitHub Container Registry:

```bash
docker pull ghcr.io/xz-dev/video_viewer_mcp:latest
docker run -p 8000:8000 -v video-data:/data ghcr.io/xz-dev/video_viewer_mcp:latest
```

Build locally:

```bash
podman build -t video-viewer-mcp -f Containerfile .
podman run -p 8000:8000 -v video-data:/data video-viewer-mcp
```

## Usage

The server exposes both MCP and REST API interfaces on port 8000.

### MCP Endpoints

- `/sse` - SSE transport
- `/mcp` - Streamable HTTP transport

### REST API

- `POST /api/download?url=<video_url>` - Download a video
- `GET /api/download/{job_id}` - Get download status
- `GET /api/downloads` - List all downloads
- `GET /api/subtitles?url=<video_url>` - Get subtitles
- `GET /api/screenshot?url=<video_url>&timestamp=<time>` - Capture screenshot
- `GET /api/health` - Health check

API documentation available at `/docs`.

### MCP Tools

| Tool | Description |
|------|-------------|
| `tool_download_video` | Download a video from URL |
| `tool_get_download_status` | Get download job status |
| `tool_list_downloads` | List all download jobs |
| `tool_get_subtitles` | Get video subtitles |
| `tool_screenshot` | Capture frame at timestamp |
| `tool_set_youtube_token` | Set YouTube cookies |
| `tool_get_youtube_token` | Get YouTube token status |
| `tool_delete_youtube_token` | Delete YouTube token |
| `tool_set_bilibili_token` | Set Bilibili SESSDATA/access_key |
| `tool_get_bilibili_token` | Get Bilibili token status |
| `tool_delete_bilibili_token` | Delete Bilibili token |

## Configuration

Configuration via environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `VIDEO_MCP_CONFIG_DIR` | Configuration directory | `~/.config/video-viewer-mcp` |
| `VIDEO_MCP_DATA_DIR` | Data directory for jobs | `~/.local/share/video-viewer-mcp` |
| `VIDEO_MCP_DOWNLOAD_DIR` | Download directory | `~/Videos/video-viewer-mcp` |

## Requirements

- Python 3.13+
- ffmpeg (for video processing)
- BBDown + .NET 8.0 (for Bilibili downloads, optional)

## License

Apache-2.0
