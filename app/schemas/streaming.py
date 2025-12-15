# app/schemas/streaming.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class VideoStreamRequest(BaseModel):
    video_id: str
    quality: Optional[str] = "auto"
    token: Optional[str] = None

class StreamResponse(BaseModel):
    url: str
    expires_at: datetime
    quality: str
    format: str = "hls"