FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including FFmpeg for video processing
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    g++ \
    ffmpeg \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Create data directories
RUN mkdir -p /app/data/videos /app/data/hls && chmod -R 777 /app/data

# Create non-root user
RUN useradd -m -u 1004 service-user && chown -R service-user:service-user /app
USER service-user

# Expose ports (8004 for API, 1935 for RTMP, 8080 for HLS)
EXPOSE 8004 1935 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8004/health || exit 1

# Run application
CMD ["uvicorn", "src.services.streaming_service.main:app", "--host", "0.0.0.0", "--port", "8004"]