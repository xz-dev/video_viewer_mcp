FROM python:3.14-slim

# Install system dependencies
# - ffmpeg: required by PyAV for video processing
# - wget: for downloading .NET installer
# - libicu76: required by .NET for globalization
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    wget \
    libicu76 \
    && rm -rf /var/lib/apt/lists/*

# Install .NET SDK (required for BBDown)
RUN wget https://dot.net/v1/dotnet-install.sh -O dotnet-install.sh \
    && chmod +x dotnet-install.sh \
    && ./dotnet-install.sh --channel 8.0 --install-dir /usr/share/dotnet \
    && rm dotnet-install.sh \
    && ln -s /usr/share/dotnet/dotnet /usr/bin/dotnet

# Install BBDown (Bilibili downloader)
ENV DOTNET_ROOT=/usr/share/dotnet
ENV PATH="${PATH}:/root/.dotnet/tools"
RUN dotnet tool install --global BBDown

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock* README.md pytest.ini ./
COPY src/ src/
COPY tests/ tests/

# Install dependencies (including dev for testing)
RUN uv sync --frozen

# Create directories for data persistence
RUN mkdir -p /data/downloads /data/jobs

# Set environment variables
ENV VIDEO_MCP_DOWNLOAD_DIR=/data/downloads
ENV VIDEO_MCP_DATA_DIR=/data

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Run the server
CMD ["uv", "run", "video-viewer-mcp"]
