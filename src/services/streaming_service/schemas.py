"""
Pydantic схемы для Streaming Service.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


# ====== Enums ======

class VideoStatus(str, Enum):
    """Статусы видео."""
    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"


class VideoQuality(str, Enum):
    """Качества видео."""
    _240P = "240p"
    _360P = "360p"
    _480P = "480p"
    _720P = "720p"
    _1080P = "1080p"
    _4K = "4k"


class StreamType(str, Enum):
    """Типы стримов."""
    HLS = "hls"
    DASH = "dash"
    DIRECT = "direct"


# ====== Схемы для видео ======

class VideoBase(BaseModel):
    """Базовая схема видео."""
    movie_id: UUID
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    original_filename: str
    duration_seconds: Optional[float] = Field(None, ge=0)
    file_size_bytes: Optional[int] = Field(None, ge=0)
    width: Optional[int] = Field(None, ge=1)
    height: Optional[int] = Field(None, ge=1)
    frame_rate: Optional[float] = Field(None, ge=0)
    bitrate: Optional[int] = Field(None, ge=0)
    codec: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class VideoCreate(VideoBase):
    """Схема для создания видео."""
    pass


class VideoUpdate(BaseModel):
    """Схема для обновления видео."""
    status: Optional[VideoStatus] = None
    duration_seconds: Optional[float] = Field(None, ge=0)
    file_size_bytes: Optional[int] = Field(None, ge=0)
    width: Optional[int] = Field(None, ge=1)
    height: Optional[int] = Field(None, ge=1)
    frame_rate: Optional[float] = Field(None, ge=0)
    bitrate: Optional[int] = Field(None, ge=0)
    codec: Optional[str] = None
    hls_playlist_url: Optional[str] = None
    dash_manifest_url: Optional[str] = None
    preview_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class VideoResponse(VideoBase):
    """Схема ответа для видео."""
    id: UUID
    status: VideoStatus
    hls_playlist_url: Optional[str]
    dash_manifest_url: Optional[str]
    preview_url: Optional[str]
    thumbnail_url: Optional[str]
    available_qualities: List[VideoQuality] = Field(default_factory=list)
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# ====== Схемы для стримов ======

class StreamRequest(BaseModel):
    """Схема запроса на стриминг."""
    movie_id: UUID
    quality: Optional[VideoQuality] = VideoQuality._720P
    start_position: float = Field(0.0, ge=0)  # Начальная позиция в секундах
    subtitles_language: Optional[str] = None
    
    @validator('quality')
    def validate_quality(cls, v):
        """Валидация качества."""
        if v:
            # Убираем префикс подчеркивания для валидации
            if v.startswith('_'):
                v = VideoQuality(v[1:])
        return v


class StreamResponse(BaseModel):
    """Схема ответа на запрос стрима."""
    movie_id: UUID
    video_id: UUID
    stream_url: str
    type: StreamType
    quality: VideoQuality
    duration_seconds: float
    available_qualities: List[VideoQuality]
    subtitles_available: List[str] = Field(default_factory=list)
    expires_at: Optional[datetime] = None  # Для временных URL
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PlaybackSession(BaseModel):
    """Схема сессии просмотра."""
    session_id: UUID
    user_id: UUID
    movie_id: UUID
    video_id: UUID
    start_time: datetime
    last_activity: datetime
    current_position: float  # Текущая позиция в секундах
    duration_watched: float  # Общее время просмотра
    quality: VideoQuality
    device_info: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# ====== Схемы для загрузки видео ======

class VideoUploadRequest(BaseModel):
    """Схема запроса на загрузку видео."""
    movie_id: UUID
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    original_filename: str
    file_size_bytes: int = Field(..., ge=1)
    metadata: Optional[Dict[str, Any]] = None


class VideoUploadResponse(BaseModel):
    """Схема ответа на запрос загрузки."""
    upload_id: UUID
    video_id: UUID
    upload_url: str
    expires_at: datetime
    chunk_size: int = 5 * 1024 * 1024  # 5MB chunks
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class VideoUploadComplete(BaseModel):
    """Схема завершения загрузки."""
    upload_id: UUID
    parts: List[Dict[str, Any]]  # Информация о частях для multipart upload


# ====== Схемы для аналитики просмотров ======

class WatchEvent(BaseModel):
    """Схема события просмотра."""
    session_id: UUID
    user_id: UUID
    movie_id: UUID
    video_id: UUID
    event_type: str = Field(..., pattern="^(start|pause|resume|seek|stop|complete)$")
    timestamp: datetime
    current_position: float
    duration_watched: float
    quality: VideoQuality
    buffer_time: Optional[float] = None  # Время буферизации
    bitrate_switch: Optional[VideoQuality] = None  # Смена качества
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class WatchStats(BaseModel):
    """Статистика просмотров."""
    movie_id: UUID
    total_views: int = 0
    total_watch_time: float = 0.0  # в секундах
    average_watch_percentage: float = 0.0  # процент просмотра
    completion_rate: float = 0.0  # процент полных просмотров
    popular_qualities: Dict[VideoQuality, int] = Field(default_factory=dict)
    last_updated: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# ====== Схемы для CDN/Storage ======

class StorageInfo(BaseModel):
    """Информация о хранилище."""
    provider: str  # "minio", "s3", "local"
    bucket: str
    base_url: str
    used_space_bytes: int
    available_space_bytes: int
    total_files: int


class CDNEdge(BaseModel):
    """Информация о CDN edge сервере."""
    location: str
    url: str
    latency_ms: Optional[float] = None
    health: str = "unknown"