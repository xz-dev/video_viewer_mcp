# Video Viewer MCP

MCP server for video viewing - download videos, extract subtitles, and capture screenshots.

## Features

- **Video Download**: Download videos from YouTube, Bilibili, and other platforms supported by yt-dlp
- **Subtitles Extraction**: Get subtitles/captions from downloaded videos (including AI-generated subtitles for Bilibili)
- **Danmaku Support**: Get bullet comments from Bilibili videos with pagination
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

### MCP Endpoint

- `/mcp` - Streamable HTTP transport

### REST API

- `POST /api/download?url=<video_url>` - Download a video
- `GET /api/download/{job_id}` - Get download status
- `GET /api/downloads` - List all downloads
- `GET /api/video-info?url=<video_url>` - Query video metadata without downloading
- `GET /api/subtitles?url=<video_url>` - Get subtitles
- `GET /api/danmaku?url=<video_url>` - Get danmaku (Bilibili bullet comments)
- `GET /api/screenshot?url=<video_url>&timestamp=<time>` - Capture screenshot
- `GET /api/health` - Health check

API documentation available at `/docs`.

### MCP Tools

| Tool | Description |
|------|-------------|
| `video_viewer_download_video` | Download a video from URL |
| `video_viewer_get_download_status` | Get download job status |
| `video_viewer_list_downloads` | List all download jobs |
| `video_viewer_get_video_info` | Query video metadata without downloading |
| `video_viewer_get_subtitles` | Get video subtitles |
| `video_viewer_get_danmaku` | Get Bilibili danmaku with pagination |
| `video_viewer_screenshot` | Capture frame at timestamp |
| `video_viewer_set_youtube_token` | Set YouTube cookies |
| `video_viewer_get_youtube_token` | Get YouTube token status |
| `video_viewer_delete_youtube_token` | Delete YouTube token |
| `video_viewer_set_bilibili_token` | Set Bilibili SESSDATA/access_key |
| `video_viewer_get_bilibili_token` | Get Bilibili token status |
| `video_viewer_delete_bilibili_token` | Delete Bilibili token |

### video_viewer_get_video_info

Query video metadata without downloading. Returns concise metadata by default (optimized for AI context understanding).

**Default fields:**
- `id`, `title`, `description`, `duration`, `chapters`
- `uploader`, `channel`, `upload_date`
- `width`, `height`, `thumbnail`
- `view_count`, `like_count`, `comment_count`
- `categories`, `tags`

**Extra fields (optional):**

Use `extra_fields` parameter to request additional data using dot notation:

| Example | Description |
|---------|-------------|
| `["formats"]` | All available formats with full details |
| `["formats.resolution"]` | Resolution of each format only |
| `["subtitles", "automatic_captions"]` | Available subtitle languages |
| `["thumbnails"]` | All thumbnail URLs |

Example MCP call:
```json
{
  "url": "https://www.youtube.com/watch?v=xxx",
  "extra_fields": ["formats.resolution", "subtitles"]
}
```

## Configuration

Configuration via environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `VIDEO_MCP_CONFIG_DIR` | Configuration directory | `~/.config/video-viewer-mcp` |
| `VIDEO_MCP_DATA_DIR` | Data directory for jobs | `~/.local/share/video-viewer-mcp` |
| `VIDEO_MCP_DOWNLOAD_DIR` | Download directory | `~/Videos/video-viewer-mcp` |

### Automatic Cleanup

video-viewer-mcp automatically cleans up expired downloaded files to free disk space.

**Default Behavior:**
- **Retention Period**: 1 day (24 hours)
- **Cleanup Schedule**: Daily at 2 AM
- **What Gets Cleaned**: Completed or failed downloads older than the retention period

**Configuration:**

Edit `~/.config/video-viewer-mcp/config.json`:

```json
{
  "cleanup": {
    "enabled": true,
    "retention_days": 1,
    "schedule": "0 2 * * *"
  }
}
```

**Options:**

- `enabled` (bool): Enable/disable automatic cleanup. Default: `true`
- `retention_days` (number): Days to retain files. Default: `1`. Supports fractional values (e.g., `0.5` for 12 hours)
- `schedule` (string): Cron expression defining cleanup time. Default: `"0 2 * * *"` (2 AM daily). Uses system timezone.

**Examples:**

Keep files for 7 days, clean at 3 AM:
```json
{
  "cleanup": {
    "retention_days": 7,
    "schedule": "0 3 * * *"
  }
}
```

Disable cleanup:
```json
{
  "cleanup": {
    "enabled": false
  }
}
```

**What Gets Cleaned:**
- ✅ Completed downloads older than retention period
- ✅ Failed downloads older than retention period
- ✅ Associated metadata (job files, URL index entries)

**What's Protected:**
- ❌ Files currently downloading
- ❌ Files within retention period

**File Age Calculation:**

Folder age is based on the **oldest file's modification time** (typically the video download time).

Example:
- Video downloaded: 2 days ago
- Subtitle added: 1 hour ago
- **Folder age**: 2 days (based on oldest file)

**Note:** Configuration changes require application restart to take effect.

## Requirements

- Python 3.13+
- ffmpeg (for video processing)
- BBDown + .NET 8.0 (for Bilibili downloads, optional)

## License

Apache-2.0
