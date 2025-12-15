"""
Модели базы данных для Streaming Service.
"""

from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime, Boolean,
    ForeignKey, Enum, JSON, LargeBinary
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from enum import Enum as PyEnum
import uuid
from src.config.database import Base


# ====== Enums для SQLAlchemy ======

class VideoStatus(PyEnum):
    """Статусы видео."""
    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"


class VideoQuality(PyEnum):
    """Качества видео."""
    _240P = "240p"
    _360P = "360p"
    _480P = "480p"
    _720P = "720p"
    _1080P = "1080p"
    _4K = "4k"


# ====== Main models ======

class Video(Base):
    """
    Модель видео файла.
    
    Attributes:
        id: UUID видео
        movie_id: ID фильма из Catalog Service
        title: Название видео
        description: Описание
        original_filename: Оригинальное имя файла
        status: Статус обработки
        duration_seconds: Длительность в секундах
        file_size_bytes: Размер файла в байтах
        width: Ширина видео
        height: Высота видео
        frame_rate: Частота кадров
        bitrate: Битрейт
        codec: Кодек видео
        hls_playlist_url: URL HLS плейлиста
        dash_manifest_url: URL DASH манифеста
        preview_url: URL превью
        thumbnail_url: URL миниатюры
        available_qualities: Доступные качества
        storage_path: Путь в хранилище
        metadata: Дополнительные метаданные
        created_at: Дата создания
        updated_at: Дата обновления
    """
    
    __tablename__ = "videos"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    movie_id = Column(UUID(as_uuid=True), nullable=False, index=True)  # Из Catalog Service
    title = Column(String(255), nullable=False)
    description = Column(Text)
    original_filename = Column(String(255), nullable=False)
    
    status = Column(
        Enum(VideoStatus),
        default=VideoStatus.UPLOADING,
        nullable=False,
        index=True
    )
    
    duration_seconds = Column(Float)
    file_size_bytes = Column(Integer)
    width = Column(Integer)
    height = Column(Integer)
    frame_rate = Column(Float)
    bitrate = Column(Integer)
    codec = Column(String(50))
    
    hls_playlist_url = Column(String(500))
    dash_manifest_url = Column(String(500))
    preview_url = Column(String(500))
    thumbnail_url = Column(String(500))
    
    available_qualities = Column(JSONB, default=[])
    storage_path = Column(String(500))
    metadata = Column(JSONB, default={})
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    segments = relationship("VideoSegment", back_populates="video", cascade="all, delete-orphan")
    playback_sessions = relationship("PlaybackSession", back_populates="video", cascade="all, delete-orphan")
    
    def to_dict(self):
        """Преобразование в словарь."""
        return {
            "id": str(self.id),
            "movie_id": str(self.movie_id),
            "title": self.title,
            "description": self.description,
            "original_filename": self.original_filename,
            "status": self.status.value,
            "duration_seconds": self.duration_seconds,
            "file_size_bytes": self.file_size_bytes,
            "width": self.width,
            "height": self.height,
            "frame_rate": self.frame_rate,
            "bitrate": self.bitrate,
            "codec": self.codec,
            "hls_playlist_url": self.hls_playlist_url,
            "dash_manifest_url": self.dash_manifest_url,
            "preview_url": self.preview_url,
            "thumbnail_url": self.thumbnail_url,
            "available_qualities": self.available_qualities,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class VideoSegment(Base):
    """
    Модель сегмента видео (для HLS/DASH).
    
    Attributes:
        id: UUID сегмента
        video_id: ID видео
        quality: Качество сегмента
        segment_number: Номер сегмента
        filename: Имя файла сегмента
        file_path: Путь к файлу
        duration_seconds: Длительность сегмента
        file_size_bytes: Размер файла
        start_time: Начальное время в видео
        end_time: Конечное время в видео
        is_key_frame: Является ли ключевым кадром
        created_at: Дата создания
    """
    
    __tablename__ = "video_segments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    video_id = Column(UUID(as_uuid=True), ForeignKey('videos.id'), nullable=False, index=True)
    quality = Column(String(20), nullable=False, index=True)
    segment_number = Column(Integer, nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500))
    duration_seconds = Column(Float)
    file_size_bytes = Column(Integer)
    start_time = Column(Float)  # Начало в секундах от начала видео
    end_time = Column(Float)    # Конец в секундах от начала видео
    is_key_frame = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    video = relationship("Video", back_populates="segments")
    
    def to_dict(self):
        """Преобразование в словарь."""
        return {
            "id": str(self.id),
            "video_id": str(self.video_id),
            "quality": self.quality,
            "segment_number": self.segment_number,
            "filename": self.filename,
            "file_path": self.file_path,
            "duration_seconds": self.duration_seconds,
            "file_size_bytes": self.file_size_bytes,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "is_key_frame": self.is_key_frame,
            "created_at": self.created_at.isoformat()
        }


class PlaybackSession(Base):
    """
    Модель сессии просмотра.
    
    Attributes:
        id: UUID сессии
        user_id: ID пользователя
        movie_id: ID фильма
        video_id: ID видео
        start_time: Время начала просмотра
        last_activity: Время последней активности
        current_position: Текущая позиция в секундах
        duration_watched: Общее время просмотра
        quality: Текущее качество
        device_info: Информация об устройстве
        ip_address: IP адрес
        user_agent: User agent
        is_active: Активна ли сессия
        ended_at: Время окончания
        created_at: Дата создания
        updated_at: Дата обновления
    """
    
    __tablename__ = "playback_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    movie_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    video_id = Column(UUID(as_uuid=True), ForeignKey('videos.id'), nullable=False, index=True)
    
    start_time = Column(DateTime(timezone=True), nullable=False)
    last_activity = Column(DateTime(timezone=True), nullable=False)
    current_position = Column(Float, default=0.0)
    duration_watched = Column(Float, default=0.0)
    quality = Column(String(20), nullable=False)
    
    device_info = Column(JSONB, default={})
    ip_address = Column(String(45))
    user_agent = Column(Text)
    
    is_active = Column(Boolean, default=True, index=True)
    ended_at = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    video = relationship("Video", back_populates="playback_sessions")
    events = relationship("PlaybackEvent", back_populates="session", cascade="all, delete-orphan")
    
    def to_dict(self):
        """Преобразование в словарь."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "movie_id": str(self.movie_id),
            "video_id": str(self.video_id),
            "start_time": self.start_time.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "current_position": self.current_position,
            "duration_watched": self.duration_watched,
            "quality": self.quality,
            "device_info": self.device_info,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "is_active": self.is_active,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class PlaybackEvent(Base):
    """
    Модель события просмотра.
    
    Attributes:
        id: UUID события
        session_id: ID сессии
        event_type: Тип события
        timestamp: Время события
        current_position: Позиция в секундах
        duration_watched: Общее время просмотра
        quality: Качество в момент события
        buffer_time: Время буферизации
        bitrate_switch: Смена битрейта
        metadata: Дополнительные метаданные
    """
    
    __tablename__ = "playback_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey('playback_sessions.id'), nullable=False, index=True)
    
    event_type = Column(String(50), nullable=False, index=True)  # start, pause, resume, seek, stop, complete
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    current_position = Column(Float, nullable=False)
    duration_watched = Column(Float, default=0.0)
    quality = Column(String(20))
    buffer_time = Column(Float)
    bitrate_switch = Column(String(20))
    metadata = Column(JSONB, default={})
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    session = relationship("PlaybackSession", back_populates="events")
    
    def to_dict(self):
        """Преобразование в словарь."""
        return {
            "id": str(self.id),
            "session_id": str(self.session_id),
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "current_position": self.current_position,
            "duration_watched": self.duration_watched,
            "quality": self.quality,
            "buffer_time": self.buffer_time,
            "bitrate_switch": self.bitrate_switch,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }


class VideoUpload(Base):
    """
    Модель загрузки видео (для multipart upload).
    
    Attributes:
        id: UUID загрузки
        video_id: ID видео
        user_id: ID пользователя
        upload_id: ID загрузки в хранилище
        status: Статус загрузки
        file_size_bytes: Общий размер файла
        uploaded_bytes: Загружено байт
        chunk_size: Размер чанка
        parts: Информация о частях
        expires_at: Время истечения
        created_at: Дата создания
        updated_at: Дата обновления
    """
    
    __tablename__ = "video_uploads"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    video_id = Column(UUID(as_uuid=True), ForeignKey('videos.id'), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    upload_id = Column(String(255), nullable=False, index=True)
    
    status = Column(String(50), default="initiated", index=True)  # initiated, uploading, completed, cancelled
    file_size_bytes = Column(Integer, nullable=False)
    uploaded_bytes = Column(Integer, default=0)
    chunk_size = Column(Integer, default=5 * 1024 * 1024)  # 5MB
    parts = Column(JSONB, default=[])
    expires_at = Column(DateTime(timezone=True), nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    video = relationship("Video")
    
    def to_dict(self):
        """Преобразование в словарь."""
        return {
            "id": str(self.id),
            "video_id": str(self.video_id),
            "user_id": str(self.user_id),
            "upload_id": self.upload_id,
            "status": self.status,
            "file_size_bytes": self.file_size_bytes,
            "uploaded_bytes": self.uploaded_bytes,
            "chunk_size": self.chunk_size,
            "parts": self.parts,
            "expires_at": self.expires_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class StorageStats(Base):
    """
    Модель статистики хранилища.
    
    Attributes:
        id: ID записи
        provider: Провайдер хранилища
        bucket: Бакет
        total_space_bytes: Общее пространство
        used_space_bytes: Использованное пространство
        total_files: Всего файлов
        total_videos: Всего видео
        last_updated: Время обновления
    """
    
    __tablename__ = "storage_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(50), nullable=False, index=True)
    bucket = Column(String(255), nullable=False, index=True)
    total_space_bytes = Column(BigInteger, default=0)
    used_space_bytes = Column(BigInteger, default=0)
    total_files = Column(Integer, default=0)
    total_videos = Column(Integer, default=0)
    last_updated = Column(DateTime(timezone=True), nullable=False)
    
    def to_dict(self):
        """Преобразование в словарь."""
        return {
            "id": self.id,
            "provider": self.provider,
            "bucket": self.bucket,
            "total_space_bytes": self.total_space_bytes,
            "used_space_bytes": self.used_space_bytes,
            "available_space_bytes": self.total_space_bytes - self.used_space_bytes,
            "used_percentage": (self.used_space_bytes / self.total_space_bytes * 100) if self.total_space_bytes > 0 else 0,
            "total_files": self.total_files,
            "total_videos": self.total_videos,
            "last_updated": self.last_updated.isoformat()
        }