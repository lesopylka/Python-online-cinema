from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class BaseEvent(BaseModel):
    """
    Базовая схема события пользовательской активности
    """
    user_id: str = Field(..., description="ID пользователя")
    movie_id: str = Field(..., description="ID фильма")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PlayEvent(BaseEvent):
    """
    Пользователь начал воспроизведение фильма
    """
    position: int = Field(0, description="Позиция старта воспроизведения в секундах")
    quality: Optional[str] = Field(None, description="Качество видео (720p, 1080p и т.д.)")


class ProgressEvent(BaseEvent):
    """
    Прогресс просмотра (отправляется периодически)
    """
    position: int = Field(..., description="Текущая позиция воспроизведения в секундах")
    buffered: Optional[int] = Field(None, description="Буферизация в секундах")


class StopEvent(BaseEvent):
    """
    Пользователь остановил просмотр
    """
    position: int = Field(..., description="Позиция остановки в секундах")
    reason: Optional[str] = Field(
        None,
        description="Причина остановки (user_exit, error, finished)"
    )


class HeartbeatEvent(BaseEvent):
    """
    Heartbeat событие для определения активной сессии
    """
    session_id: str = Field(..., description="ID сессии просмотра")
    position: int = Field(..., description="Текущая позиция воспроизведения")


class ErrorEvent(BaseEvent):
    """
    Ошибка при воспроизведении
    """
    error_code: str = Field(..., description="Код ошибки")
    message: Optional[str] = Field(None, description="Описание ошибки")
