"""
Pydantic схемы для Catalog Service.
"""

from pydantic import BaseModel, Field, validator, root_validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from enum import Enum
from uuid import UUID
import re


# ====== Enums ======

class ContentType(str, Enum):
    """Типы контента."""
    MOVIE = "movie"
    SERIES = "series"
    DOCUMENTARY = "documentary"
    SHORT = "short"
    ANIMATION = "animation"


class AgeRating(str, Enum):
    """Возрастные рейтинги."""
    G = "G"        # Для всех возрастов
    PG = "PG"      # Родительский контроль
    PG13 = "PG-13" # Детям до 13 с родителями
    R = "R"        # Ограничение 17+
    NC17 = "NC-17" # Только для взрослых


# ====== Базовые схемы ======

class GenreBase(BaseModel):
    """Базовая схема жанра."""
    name: str = Field(..., min_length=1, max_length=50)
    slug: str = Field(..., min_length=1, max_length=50, regex=r'^[a-z0-9-]+$')
    description: Optional[str] = None
    icon_url: Optional[str] = None
    
    @validator('slug')
    def validate_slug(cls, v):
        """Валидация slug."""
        if not re.match(r'^[a-z0-9-]+$', v):
            raise ValueError('Slug can only contain lowercase letters, numbers and hyphens')
        return v


class PersonBase(BaseModel):
    """Базовая схема человека."""
    full_name: str = Field(..., min_length=1, max_length=255)
    birth_date: Optional[datetime] = None
    birth_place: Optional[str] = Field(None, max_length=255)
    death_date: Optional[datetime] = None
    biography: Optional[str] = None
    photo_url: Optional[str] = None
    imdb_id: Optional[str] = Field(None, max_length=20)


class MovieBase(BaseModel):
    """Базовая схема фильма."""
    title: str = Field(..., min_length=1, max_length=255)
    original_title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    content_type: ContentType = ContentType.MOVIE
    release_year: Optional[int] = Field(None, ge=1888, le=2100)  # Первый фильм 1888
    duration_minutes: Optional[int] = Field(None, ge=1, le=1000)
    age_rating: AgeRating = AgeRating.PG13
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    trailer_url: Optional[str] = None
    country: Optional[str] = Field(None, max_length=100)
    language: Optional[str] = Field(None, max_length=50)
    subtitles: List[str] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None
    
    @validator('release_year')
    def validate_release_year(cls, v):
        """Валидация года выпуска."""
        if v and v > datetime.now().year + 5:
            raise ValueError('Release year cannot be more than 5 years in the future')
        return v
    
    @validator('poster_url', 'backdrop_url', 'trailer_url')
    def validate_url(cls, v):
        """Валидация URL."""
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v


class SeasonBase(BaseModel):
    """Базовая схема сезона."""
    season_number: int = Field(..., ge=1)
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    episode_count: Optional[int] = Field(None, ge=0)
    release_year: Optional[int] = Field(None, ge=1888, le=2100)
    poster_url: Optional[str] = None


class EpisodeBase(BaseModel):
    """Базовая схема серии."""
    episode_number: int = Field(..., ge=1)
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    duration_minutes: Optional[int] = Field(None, ge=1, le=500)
    video_url: Optional[str] = None
    release_date: Optional[datetime] = None
    
    @validator('video_url')
    def validate_video_url(cls, v):
        """Валидация URL видео."""
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError('Video URL must start with http:// or https://')
        return v


class ReviewBase(BaseModel):
    """Базовая схема отзыва."""
    rating: int = Field(..., ge=1, le=5)
    title: Optional[str] = Field(None, max_length=255)
    comment: Optional[str] = None


# ====== Схемы для создания ======

class GenreCreate(GenreBase):
    """Схема для создания жанра."""
    pass


class PersonCreate(PersonBase):
    """Схема для создания человека."""
    pass


class MovieCreate(MovieBase):
    """Схема для создания фильма."""
    genre_ids: List[int] = Field(default_factory=list)
    actor_ids: List[UUID] = Field(default_factory=list)
    director_ids: List[UUID] = Field(default_factory=list)
    writer_ids: List[UUID] = Field(default_factory=list)


class SeasonCreate(SeasonBase):
    """Схема для создания сезона."""
    pass


class EpisodeCreate(EpisodeBase):
    """Схема для создания серии."""
    pass


class ReviewCreate(ReviewBase):
    """Схема для создания отзыва."""
    movie_id: UUID


class WatchlistCreate(BaseModel):
    """Схема для добавления в список просмотра."""
    movie_id: UUID
    notes: Optional[str] = None


# ====== Схемы для обновления ======

class GenreUpdate(BaseModel):
    """Схема для обновления жанра."""
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = None
    icon_url: Optional[str] = None
    is_active: Optional[bool] = None


class PersonUpdate(BaseModel):
    """Схема для обновления человека."""
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    birth_date: Optional[datetime] = None
    birth_place: Optional[str] = Field(None, max_length=255)
    death_date: Optional[datetime] = None
    biography: Optional[str] = None
    photo_url: Optional[str] = None
    imdb_id: Optional[str] = Field(None, max_length=20)
    is_active: Optional[bool] = None


class MovieUpdate(BaseModel):
    """Схема для обновления фильма."""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    original_title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    release_year: Optional[int] = Field(None, ge=1888, le=2100)
    duration_minutes: Optional[int] = Field(None, ge=1, le=1000)
    rating: Optional[float] = Field(None, ge=0.0, le=10.0)
    age_rating: Optional[AgeRating] = None
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    trailer_url: Optional[str] = None
    video_url: Optional[str] = None
    country: Optional[str] = Field(None, max_length=100)
    language: Optional[str] = Field(None, max_length=50)
    subtitles: Optional[List[str]] = None
    is_active: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None
    genre_ids: Optional[List[int]] = None
    actor_ids: Optional[List[UUID]] = None
    director_ids: Optional[List[UUID]] = None
    writer_ids: Optional[List[UUID]] = None


class SeasonUpdate(BaseModel):
    """Схема для обновления сезона."""
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    episode_count: Optional[int] = Field(None, ge=0)
    release_year: Optional[int] = Field(None, ge=1888, le=2100)
    poster_url: Optional[str] = None


class EpisodeUpdate(BaseModel):
    """Схема для обновления серии."""
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    duration_minutes: Optional[int] = Field(None, ge=1, le=500)
    video_url: Optional[str] = None
    release_date: Optional[datetime] = None


class ReviewUpdate(BaseModel):
    """Схема для обновления отзыва."""
    rating: Optional[int] = Field(None, ge=1, le=5)
    title: Optional[str] = Field(None, max_length=255)
    comment: Optional[str] = None
    is_active: Optional[bool] = None


# ====== Схемы для ответов ======

class GenreResponse(GenreBase):
    """Схема ответа для жанра."""
    id: int
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PersonResponse(PersonBase):
    """Схема ответа для человека."""
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class MovieResponse(MovieBase):
    """Схема ответа для фильма."""
    id: UUID
    rating: float
    video_url: Optional[str]
    is_active: bool
    genres: List[GenreResponse] = []
    actors: List[PersonResponse] = []
    directors: List[PersonResponse] = []
    writers: List[PersonResponse] = []
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SeasonResponse(SeasonBase):
    """Схема ответа для сезона."""
    id: UUID
    movie_id: UUID
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class EpisodeResponse(EpisodeBase):
    """Схема ответа для серии."""
    id: UUID
    season_id: UUID
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ReviewResponse(ReviewBase):
    """Схема ответа для отзыва."""
    id: UUID
    movie_id: UUID
    user_id: UUID
    likes_count: int
    is_verified: bool
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class WatchlistResponse(BaseModel):
    """Схема ответа для списка просмотра."""
    id: UUID
    user_id: UUID
    movie_id: UUID
    added_at: datetime
    notes: Optional[str]
    movie: MovieResponse
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# ====== Схемы с вложенными объектами ======

class MovieDetailResponse(MovieResponse):
    """Детальная схема фильма с сезонами."""
    seasons: List[SeasonResponse] = []
    reviews: List[ReviewResponse] = []


class SeasonDetailResponse(SeasonResponse):
    """Детальная схема сезона с сериями."""
    episodes: List[EpisodeResponse] = []


# ====== Схемы для поиска и фильтрации ======

class MovieSearchParams(BaseModel):
    """Параметры поиска фильмов."""
    query: Optional[str] = None
    genre_ids: Optional[List[int]] = None
    content_type: Optional[ContentType] = None
    min_rating: Optional[float] = Field(None, ge=0.0, le=10.0)
    max_rating: Optional[float] = Field(None, ge=0.0, le=10.0)
    year_from: Optional[int] = Field(None, ge=1888, le=2100)
    year_to: Optional[int] = Field(None, ge=1888, le=2100)
    country: Optional[str] = None
    language: Optional[str] = None
    age_rating: Optional[AgeRating] = None
    sort_by: Optional[str] = Field(None, pattern='^(title|rating|release_year|created_at)$')
    sort_order: Optional[str] = Field('desc', pattern='^(asc|desc)$')
    page: int = Field(1, ge=1)
    size: int = Field(20, ge=1, le=100)
    
    @root_validator
    def validate_rating_range(cls, values):
        """Валидация диапазона рейтинга."""
        min_rating = values.get('min_rating')
        max_rating = values.get('max_rating')
        
        if min_rating is not None and max_rating is not None:
            if min_rating > max_rating:
                raise ValueError('min_rating cannot be greater than max_rating')
        
        return values
    
    @root_validator
    def validate_year_range(cls, values):
        """Валидация диапазона лет."""
        year_from = values.get('year_from')
        year_to = values.get('year_to')
        
        if year_from is not None and year_to is not None:
            if year_from > year_to:
                raise ValueError('year_from cannot be greater than year_to')
        
        return values


class PersonSearchParams(BaseModel):
    """Параметры поиска людей."""
    query: Optional[str] = None
    role: Optional[str] = Field(None, pattern='^(actor|director|writer)$')
    page: int = Field(1, ge=1)
    size: int = Field(20, ge=1, le=100)


class GenreFilterParams(BaseModel):
    """Параметры фильтрации жанров."""
    is_active: Optional[bool] = None
    page: int = Field(1, ge=1)
    size: int = Field(50, ge=1, le=100)


# ====== Схемы для статистики ======

class MovieStatsResponse(BaseModel):
    """Статистика фильма."""
    movie_id: UUID
    total_views: int = 0
    total_watch_time: int = 0  # в секундах
    average_rating: float = 0.0
    total_reviews: int = 0
    watchlist_count: int = 0
    last_updated: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class GenreStatsResponse(BaseModel):
    """Статистика по жанрам."""
    genre_id: int
    genre_name: str
    movie_count: int
    average_rating: float
    total_views: int


# ====== Схемы для экспорта ======

class MovieExportResponse(BaseModel):
    """Схема для экспорта фильмов."""
    id: UUID
    title: str
    original_title: Optional[str]
    description: Optional[str]
    content_type: str
    release_year: Optional[int]
    duration_minutes: Optional[int]
    rating: float
    age_rating: str
    country: Optional[str]
    language: Optional[str]
    genres: List[str]
    actors: List[str]
    directors: List[str]
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }