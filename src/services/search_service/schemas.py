"""
Pydantic схемы для Search Service.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from enum import Enum
from uuid import UUID


# ====== Enums ======

class SearchSortField(str, Enum):
    """Поля для сортировки результатов поиска."""
    RELEVANCE = "relevance"
    TITLE = "title"
    RATING = "rating"
    RELEASE_YEAR = "release_year"
    CREATED_AT = "created_at"


class SearchSortOrder(str, Enum):
    """Порядок сортировки."""
    ASC = "asc"
    DESC = "desc"


# ====== Схемы поиска ======

class SearchQuery(BaseModel):
    """Схема поискового запроса."""
    query: Optional[str] = Field(None, min_length=1, max_length=200)
    genre_ids: Optional[List[int]] = None
    content_type: Optional[str] = Field(None, pattern="^(movie|series|documentary|short|animation)$")
    min_rating: Optional[float] = Field(None, ge=0.0, le=10.0)
    max_rating: Optional[float] = Field(None, ge=0.0, le=10.0)
    year_from: Optional[int] = Field(None, ge=1888, le=2100)
    year_to: Optional[int] = Field(None, ge=1888, le=2100)
    country: Optional[str] = None
    language: Optional[str] = None
    age_rating: Optional[str] = Field(None, pattern="^(G|PG|PG-13|R|NC-17)$")
    sort_by: SearchSortField = SearchSortField.RELEVANCE
    sort_order: SearchSortOrder = SearchSortOrder.DESC
    page: int = Field(1, ge=1)
    size: int = Field(20, ge=1, le=100)
    
    @validator('max_rating')
    def validate_max_rating(cls, v, values):
        """Валидация максимального рейтинга."""
        if 'min_rating' in values and values['min_rating'] is not None and v is not None:
            if v < values['min_rating']:
                raise ValueError('max_rating must be greater than or equal to min_rating')
        return v
    
    @validator('year_to')
    def validate_year_to(cls, v, values):
        """Валидация конечного года."""
        if 'year_from' in values and values['year_from'] is not None and v is not None:
            if v < values['year_from']:
                raise ValueError('year_to must be greater than or equal to year_from')
        return v


class AutocompleteQuery(BaseModel):
    """Схема запроса автодополнения."""
    query: str = Field(..., min_length=1, max_length=100)
    size: int = Field(10, ge=1, le=20)
    content_type: Optional[str] = Field(None, pattern="^(movie|series|documentary|short|animation)$")


# ====== Схемы ответов ======

class SearchResult(BaseModel):
    """Схема результата поиска."""
    id: str
    title: str
    original_title: Optional[str]
    description: Optional[str]
    content_type: str
    release_year: Optional[int]
    duration_minutes: Optional[int]
    rating: float
    age_rating: str
    poster_url: Optional[str]
    backdrop_url: Optional[str]
    country: Optional[str]
    language: Optional[str]
    genres: List[Dict[str, Any]]
    actors: List[Dict[str, Any]]
    directors: List[Dict[str, Any]]
    created_at: str
    updated_at: Optional[str]
    score: float = 0.0  # Релевантность
    
    class Config:
        json_encoders = {
            UUID: lambda v: str(v)
        }


class SearchResponse(BaseModel):
    """Схема ответа на поисковый запрос."""
    query: Optional[str]
    results: List[SearchResult]
    total: int
    page: int
    size: int
    pages: int
    took: int  # Время выполнения в миллисекундах
    filters: Optional[Dict[str, Any]] = None
    
    @validator('pages', always=True)
    def calculate_pages(cls, v, values):
        """Вычисление количества страниц."""
        if 'total' in values and 'size' in values:
            total = values['total']
            size = values['size']
            return (total + size - 1) // size  # ceil division
        return v


class AutocompleteResult(BaseModel):
    """Схема результата автодополнения."""
    text: str
    score: float
    source: Optional[Dict[str, Any]] = None


class AutocompleteResponse(BaseModel):
    """Схема ответа на автодополнение."""
    query: str
    suggestions: List[AutocompleteResult]
    took: int  # Время выполнения в миллисекундах


class SimilarMoviesResponse(BaseModel):
    """Схема ответа на поиск похожих фильмов."""
    movie_id: str
    similar_movies: List[SearchResult]
    total: int
    took: int


class IndexStatsResponse(BaseModel):
    """Схема статистики индекса."""
    index_name: str
    total_documents: int
    total_size: int  # в байтах
    total_size_mb: float
    health: str
    
    @validator('total_size_mb', always=True)
    def calculate_mb(cls, v, values):
        """Вычисление размера в мегабайтах."""
        if 'total_size' in values:
            return round(values['total_size'] / (1024 * 1024), 2)
        return 0.0


# ====== Схемы для событий ======

class MovieIndexEvent(BaseModel):
    """Схема события индексации фильма."""
    action: str = Field(..., pattern="^(index|update|delete)$")
    movie_id: str
    movie_data: Optional[Dict[str, Any]] = None
    timestamp: str


class SearchAnalyticsEvent(BaseModel):
    """Схема события аналитики поиска."""
    query: str
    filters: Optional[Dict[str, Any]] = None
    results_count: int
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    timestamp: str