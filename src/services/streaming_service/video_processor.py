"""
Video processor for handling video transcoding and HLS packaging.
"""

import os
import asyncio
import subprocess
import shutil
from typing import Dict, List, Optional
import uuid
from datetime import datetime
import logging

from .schemas import StreamInfo, Quality, VideoQuality
from .models import Video

logger = logging.getLogger(__name__)

class VideoProcessor:
    """Handles video processing and streaming."""
    
    def __init__(self, base_path: str = "/app/data"):
        self.base_path = base_path
        self.videos_path = os.path.join(base_path, "videos")
        self.hls_path = os.path.join(base_path, "hls")
        self._ensure_directories()
        
    def _ensure_directories(self):
        """Ensure necessary directories exist."""
        os.makedirs(self.videos_path, exist_ok=True)
        os.makedirs(self.hls_path, exist_ok=True)
        
    async def initialize(self):
        """Initialize the video processor."""
        logger.info("Video processor initialized")
        
    async def process_video(self, source_file_id: str, video_id: str) -> Dict[str, str]:
        """
        Process video file: transcode to multiple qualities and create HLS segments.
        
        Args:
            source_file_id: ID of the source file in storage
            video_id: Unique video ID
            
        Returns:
            Dictionary of processed file paths
        """
        logger.info(f"Processing video {video_id} from file {source_file_id}")
        
        # Create video directory
        video_dir = os.path.join(self.hls_path, video_id)
        os.makedirs(video_dir, exist_ok=True)
        
        # Define output qualities
        qualities = [
            Quality(name="360p", height=360, bitrate="600k"),
            Quality(name="480p", height=480, bitrate="1000k"),
            Quality(name="720p", height=720, bitrate="2500k"),
            Quality(name="1080p", height=1080, bitrate="5000k"),
        ]
        
        processed_files = {}
        
        # Process each quality
        for quality in qualities:
            quality_dir = os.path.join(video_dir, quality.name)
            os.makedirs(quality_dir, exist_ok=True)
            
            # FFmpeg command for HLS transcoding
            cmd = [
                "ffmpeg",
                "-i", os.path.join(self.videos_path, f"{source_file_id}.mp4"),
                "-vf", f"scale=-2:{quality.height}",
                "-c:v", "libx264",
                "-b:v", quality.bitrate,
                "-c:a", "aac",
                "-b:a", "128k",
                "-f", "hls",
                "-hls_time", "10",
                "-hls_playlist_type", "vod",
                "-hls_segment_filename", os.path.join(quality_dir, "segment_%03d.ts"),
                os.path.join(quality_dir, "playlist.m3u8")
            ]
            
            try:
                # Run ffmpeg command
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                logger.info(f"Processed {quality.name} for video {video_id}")
                
                processed_files[quality.name] = quality_dir
                
            except subprocess.CalledProcessError as e:
                logger.error(f"Error processing {quality.name}: {e.stderr}")
                raise RuntimeError(f"Failed to process video quality {quality.name}")
        
        # Create master playlist
        master_playlist = self._create_master_playlist(video_id, qualities)
        master_path = os.path.join(video_dir, "master.m3u8")
        
        with open(master_path, "w") as f:
            f.write(master_playlist)
        
        logger.info(f"Video {video_id} processing complete")
        return processed_files
    
    def _create_master_playlist(self, video_id: str, qualities: List[Quality]) -> str:
        """Create HLS master playlist."""
        lines = ["#EXTM3U", "#EXT-X-VERSION:3"]
        
        for quality in qualities:
            lines.extend([
                f"#EXT-X-STREAM-INF:BANDWIDTH={self._get_bandwidth(quality.bitrate)},RESOLUTION={self._get_resolution(quality.height)}",
                f"{quality.name}/playlist.m3u8"
            ])
        
        return "\n".join(lines)
    
    def _get_bandwidth(self, bitrate: str) -> int:
        """Convert bitrate string to bandwidth integer."""
        if bitrate.endswith("k"):
            return int(bitrate[:-1]) * 1000
        elif bitrate.endswith("M"):
            return int(bitrate[:-1]) * 1000000
        return int(bitrate)
    
    def _get_resolution(self, height: int) -> str:
        """Get resolution string from height."""
        if height == 360:
            return "640x360"
        elif height == 480:
            return "854x480"
        elif height == 720:
            return "1280x720"
        elif height == 1080:
            return "1920x1080"
        return f"1920x{height}"
    
    async def generate_stream_info(self, video_id: str) -> StreamInfo:
        """Generate streaming information for a video."""
        video_dir = os.path.join(self.hls_path, video_id)
        
        if not os.path.exists(video_dir):
            raise FileNotFoundError(f"Video {video_id} not found")
        
        # List available qualities
        qualities = []
        for quality_name in ["360p", "480p", "720p", "1080p"]:
            quality_dir = os.path.join(video_dir, quality_name)
            if os.path.exists(quality_dir):
                qualities.append(
                    VideoQuality(
                        name=quality_name,
                        playlist_url=f"/stream/{video_id}/{quality_name}/playlist.m3u8",
                        bandwidth=self._get_bandwidth_for_quality(quality_name)
                    )
                )
        
        return StreamInfo(
            video_id=video_id,
            master_playlist_url=f"/stream/{video_id}/master.m3u8",
            qualities=qualities,
            duration=self._get_video_duration(video_id)
        )
    
    def _get_bandwidth_for_quality(self, quality_name: str) -> int:
        """Get bandwidth for quality."""
        bandwidths = {
            "360p": 600000,
            "480p": 1000000,
            "720p": 2500000,
            "1080p": 5000000,
        }
        return bandwidths.get(quality_name, 1000000)
    
    def _get_video_duration(self, video_id: str) -> Optional[float]:
        """Get video duration in seconds."""
        # In production, extract duration from video metadata
        return None  # Implement based on your needs
    
    async def get_master_playlist(self, video_id: str) -> str:
        """Get path to master playlist."""
        master_path = os.path.join(self.hls_path, video_id, "master.m3u8")
        if not os.path.exists(master_path):
            raise FileNotFoundError(f"Master playlist not found for video {video_id}")
        return master_path
    
    async def get_segment_path(self, video_id: str, quality: str, segment: str) -> str:
        """Get path to video segment."""
        segment_path = os.path.join(self.hls_path, video_id, quality, segment)
        if not os.path.exists(segment_path):
            raise FileNotFoundError(f"Segment {segment} not found")
        return segment_path
    
    async def get_stream_info(self, video_id: str) -> StreamInfo:
        """Get streaming information for a video."""
        return await self.generate_stream_info(video_id)
    
    async def delete_video(self, video_id: str):
        """Delete video files."""
        video_dir = os.path.join(self.hls_path, video_id)
        if os.path.exists(video_dir):
            shutil.rmtree(video_dir)
            logger.info(f"Deleted video {video_id}")

# Singleton instance
_video_processor: Optional[VideoProcessor] = None

def get_video_processor() -> VideoProcessor:
    """Get video processor instance."""
    global _video_processor
    if _video_processor is None:
        _video_processor = VideoProcessor()
    return _video_processor