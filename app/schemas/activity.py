# app/schemas/activity.py
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class EventType(str, Enum):
    """Типы событий пользовательской активности"""
    PAGE_VIEW = "page_view"
    VIDEO_PLAY = "video_play"
    VIDEO_PAUSE = "video_pause"
    VIDEO_STOP = "video_stop"
    VIDEO_SEEK = "video_seek"
    VIDEO_COMPLETE = "video_complete"
    SEARCH = "search"
    RATING = "rating"
    COMMENT = "comment"
    LIKE = "like"
    SHARE = "share"
    SUBSCRIPTION = "subscription"
    PURCHASE = "purchase"


class ActivityEvent(BaseModel):
    """Схема для одного события активности"""
    event_type: EventType = Field(..., description="Тип события")
    event_name: str = Field(..., description="Название события", max_length=255)

    # Идентификаторы
    user_id: Optional[str] = Field(None, description="ID пользователя (анонимизированный)")
    session_id: Optional[str] = Field(None, description="ID сессии")
    device_id: Optional[str] = Field(None, description="ID устройства")

    # Контекст
    page_url: Optional[str] = Field(None, description="URL страницы")
    referrer_url: Optional[str] = Field(None, description="URL реферера")
    content_id: Optional[str] = Field(None, description="ID контента (фильма)")
    content_type: Optional[str] = Field(None, description="Тип контента")

    # Метаданные
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Дополнительные данные")

    # Временные метки и значения
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Время события")
    duration: Optional[float] = Field(None, ge=0, description="Длительность в секундах")
    value: Optional[float] = Field(None, description="Числовое значение события")

    # Валидаторы
    @validator('metadata')
    def validate_metadata(cls, v):
        """Ограничиваем размер метаданных"""
        if v and len(str(v)) > 5000:
            raise ValueError('Metadata too large (max 5000 chars)')
        return v

    @validator('user_agent', check_fields=False)
    def validate_user_agent(cls, v):
        """Валидация user_agent (добавляется в обогащении)"""
        if v and len(v) > 500:
            return v[:500]
        return v

    class Config:
        schema_extra = {
            "example": {
                "event_type": "video_play",
                "event_name": "Просмотр фильма 'Интерстеллар'",
                "user_id": "user_123",
                "session_id": "session_abc",
                "device_id": "web_chrome_linux",
                "content_id": "movie_456",
                "content_type": "movie",
                "metadata": {
                    "current_time": 120.5,
                    "duration": 8460,
                    "quality": "1080p"
                },
                "duration": 120.5,
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }


class ActivityBatch(BaseModel):
    """Схема для пачки событий"""
    events: List[ActivityEvent] = Field(..., description="Список событий")

    @validator('events')
    def validate_batch_size(cls, v):
        """Ограничиваем размер пачки"""
        if len(v) > 1000:
            raise ValueError('Batch size too large (max 1000 events)')
        return v

    class Config:
        schema_extra = {
            "example": {
                "events": [
                    {
                        "event_type": "page_view",
                        "event_name": "Главная страница",
                        "page_url": "https://cinema.example.com/"
                    },
                    {
                        "event_type": "video_play",
                        "event_name": "Запуск видео",
                        "content_id": "movie_123"
                    }
                ]
            }
        }


class ActivityResponse(BaseModel):
    """Схема ответа на запрос сбора активности"""
    status: str = Field(..., description="Статус обработки")
    message: str = Field(..., description="Сообщение")
    accepted_count: int = Field(..., description="Количество принятых событий")
    batch_id: Optional[str] = Field(None, description="ID пачки для отслеживания")
    processing_time_ms: Optional[float] = Field(None, description="Время обработки в мс")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Время ответа")


class SessionActivity(BaseModel):
    """Схема активности сессии"""
    session_id: str
    user_id: Optional[str]
    start_time: datetime
    end_time: Optional[datetime]
    event_count: int
    events: List[Dict[str, Any]]


class UserActivityStats(BaseModel):
    """Статистика активности пользователя"""
    user_id: str
    total_events: int
    sessions_count: int
    video_plays: int
    last_activity: Optional[datetime]
    period_start: datetime
    period_end: datetime