"""
Streaming Service - handles video streaming and processing.
"""

import os
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uuid
from typing import Optional, List

from src.shared.logging import setup_logging
from src.shared.exceptions import setup_exception_handlers
from src.monitoring.metrics import setup_metrics, monitor_request
from src.monitoring.tracing import setup_tracing
from src.shared.kafka_producer import KafkaProducer

from .schemas import (
    VideoUploadResponse,
    VideoMetadata,
    StreamInfo,
    PlaylistRequest,
    Quality
)
from .models import Video
from .storage_client import StorageClient, get_storage_client
from .video_processor import VideoProcessor, get_video_processor

# Setup
logger = setup_logging(__name__)
app = FastAPI(
    title="Streaming Service",
    description="Handles video streaming and processing",
    version="1.0.0",
)

# Middleware
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
setup_metrics(app)
setup_tracing(app)
setup_exception_handlers(app)

# Kafka producer for analytics events
kafka_producer = KafkaProducer()

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("Starting Streaming Service")
    # Initialize storage client
    storage_client = get_storage_client()
    await storage_client.initialize()
    
    # Initialize video processor
    video_processor = get_video_processor()
    await video_processor.initialize()

@app.get("/")
async def root():
    return {"service": "streaming-service", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@monitor_request
@app.post("/upload", response_model=VideoUploadResponse)
async def upload_video(
    file_id: str,
    title: str,
    storage_client: StorageClient = Depends(get_storage_client),
    video_processor: VideoProcessor = Depends(get_video_processor)
):
    """
    Upload a video file and process it for streaming.
    Note: Actual file upload should be done via presigned URL from storage service.
    """
    try:
        # Generate unique video ID
        video_id = str(uuid.uuid4())
        
        # Create video metadata
        video = Video(
            id=video_id,
            file_id=file_id,
            title=title,
            status="uploading"
        )
        
        # Process video for different qualities
        processed_files = await video_processor.process_video(file_id, video_id)
        
        # Update video status
        video.status = "processed"
        video.processed_files = processed_files
        
        # Generate streaming URLs
        stream_info = await video_processor.generate_stream_info(video_id)
        
        # Send analytics event
        await kafka_producer.send_event("video_uploaded", {
            "video_id": video_id,
            "title": title,
            "timestamp": str(video.created_at)
        })
        
        return VideoUploadResponse(
            video_id=video_id,
            stream_url=f"/stream/{video_id}/master.m3u8",
            qualities=stream_info.qualities,
            message="Video uploaded and processed successfully"
        )
        
    except Exception as e:
        logger.error(f"Error uploading video: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to upload video")

@monitor_request
@app.get("/stream/{video_id}/master.m3u8")
async def get_master_playlist(
    video_id: str,
    video_processor: VideoProcessor = Depends(get_video_processor)
):
    """Get master HLS playlist for a video."""
    try:
        playlist_path = await video_processor.get_master_playlist(video_id)
        
        if not os.path.exists(playlist_path):
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Send analytics event for stream start
        await kafka_producer.send_event("stream_started", {
            "video_id": video_id,
            "timestamp": str(uuid.uuid4())  # Use actual timestamp in production
        })
        
        return FileResponse(
            playlist_path,
            media_type="application/vnd.apple.mpegurl",
            headers={"Cache-Control": "public, max-age=3600"}
        )
        
    except Exception as e:
        logger.error(f"Error getting playlist: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get playlist")

@monitor_request
@app.get("/stream/{video_id}/{quality}/{segment}")
async def get_video_segment(
    video_id: str,
    quality: str,
    segment: str,
    video_processor: VideoProcessor = Depends(get_video_processor)
):
    """Get a video segment for specific quality."""
    try:
        segment_path = await video_processor.get_segment_path(video_id, quality, segment)
        
        if not os.path.exists(segment_path):
            raise HTTPException(status_code=404, detail="Segment not found")
        
        return FileResponse(
            segment_path,
            media_type="video/MP2T",
            headers={"Cache-Control": "public, max-age=31536000"}  # 1 year cache for segments
        )
        
    except Exception as e:
        logger.error(f"Error getting segment: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get segment")

@monitor_request
@app.get("/videos/{video_id}/info")
async def get_video_info(
    video_id: str,
    video_processor: VideoProcessor = Depends(get_video_processor)
):
    """Get video metadata and streaming information."""
    try:
        stream_info = await video_processor.get_stream_info(video_id)
        return stream_info
    except Exception as e:
        logger.error(f"Error getting video info: {str(e)}")
        raise HTTPException(status_code=404, detail="Video not found")

@monitor_request
@app.delete("/videos/{video_id}")
async def delete_video(
    video_id: str,
    storage_client: StorageClient = Depends(get_storage_client),
    video_processor: VideoProcessor = Depends(get_video_processor)
):
    """Delete a video and all associated files."""
    try:
        await video_processor.delete_video(video_id)
        await storage_client.delete_video(video_id)
        
        # Send analytics event
        await kafka_producer.send_event("video_deleted", {
            "video_id": video_id,
            "timestamp": str(uuid.uuid4())
        })
        
        return {"message": "Video deleted successfully"}
        
    except Exception as e:
        logger.error(f"Error deleting video: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete video")

@app.get("/metrics")
async def get_metrics():
    """Get Prometheus metrics."""
    from src.monitoring.metrics import generate_metrics
    return generate_metrics()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)