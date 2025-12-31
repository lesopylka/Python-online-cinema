from pydantic import BaseModel
from typing import Optional


class BaseEventSchema(BaseModel):
    user_id: str
    movie_id: str
    timestamp: Optional[str] = None


class PlayEventSchema(BaseEventSchema):
    pass


class ProgressEventSchema(BaseEventSchema):
    progress: int


class StopEventSchema(BaseEventSchema):
    duration: Optional[int] = None


class HeartbeatSchema(BaseEventSchema):
    session_id: str
    bitrate: Optional[int] = None


class ErrorEventSchema(BaseEventSchema):
    error_code: str
    error_message: str
