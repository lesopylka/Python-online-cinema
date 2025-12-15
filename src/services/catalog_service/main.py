"""
Основной файл Catalog Service.
"""

import logging
from datetime import datetime
from uuid import UUID
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Request, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.config.database import get_db, engine
from src.config.settings import settings
from src.shared.logging import setup_logging
from src.shared.exceptions import ServiceException
from src.shared.schemas import (
    PaginatedResponse, SuccessResponse, ErrorResponse,
    HealthCheck, Status
)
from src.monitoring.metrics import setup_metrics
from src.monitoring.tracing import setup_tracing

from . import models, schemas, crud
from .models import Base
from .dependencies import get_current_user, require_admin, get_pagination_params

# Настройка логирования
setup_logging("catalog-service")
logger = logging.getLogger(__name__)

# Создание таблиц
Base.metadata.create_all(bind=engine)

# Создание приложения
app = FastAPI(
    title="Catalog Service",
    description="Сервис управления каталогом фильмов онлайн-кинотеатра",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Настройка метрик
setup_metrics(app)

# Настройка трассировки
setup_tracing(app)


# ====== Exception handlers ======

@app.exception_handler(ServiceException)
async def service_exception_handler(request: Request, exc: ServiceException):
    """Обработчик кастомных исключений."""
    logger.warning(f"Service exception: {exc.message}", extra={"code": exc.code})
    
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            detail=exc.message,
            code=exc.code,
            errors=exc.details.get("errors") if "errors" in exc.details else None
        ).dict()
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Обработчик HTTP исключений."""
    logger.warning(f"HTTP exception: {exc.detail}")
    
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            detail=exc.detail,
            status_code=exc.status_code
        ).dict()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Обработчик непредвиденных исключений."""
    logger.exception(f"Unexpected error: {str(exc)}")
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            detail="Internal server error",
            code="INTERNAL_ERROR"
        ).dict()
    )


# ====== Health check ======

@app.get("/", include_in_schema=False)
async def root():
    """Корневой endpoint."""
    return {
        "message": "Catalog Service",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health")
async def health_check(db: Session = Depends(get_db)) -> HealthCheck:
    """
    Health check endpoint.
    Проверяет подключение к базе данных.
    """
    dependencies_status = {}
    
    # Проверка базы данных
    try:
        db.execute("SELECT 1")
        dependencies_status["database"] = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        dependencies_status["database"] = "unhealthy"
    
    return HealthCheck(
        status="healthy" if all(v == "healthy" for v in dependencies_status.values()) else "degraded",
        service="catalog-service",
        version="1.0.0",
        dependencies=dependencies_status
    )


# ====== Movies endpoints ======

@app.get("/api/v1/movies", response_model=SuccessResponse[PaginatedResponse[schemas.MovieResponse]])
async def get_movies(
    search_params: schemas.MovieSearchParams = Depends(),
    db: Session = Depends(get_db)
):
    """
    Получение списка фильмов с фильтрацией и пагинацией.
    
    Query Parameters:
        query: Поисковый запрос (название, описание)
        genre_ids: Список ID жанров
        content_type: Тип контента
        min_rating: Минимальный рейтинг
        max_rating: Максимальный рейтинг
        year_from: Год от
        year_to: Год до
        country: Страна
        language: Язык
        age_rating: Возрастной рейтинг
        sort_by: Поле сортировки (title, rating, release_year, created_at)
        sort_order: Порядок сортировки (asc, desc)
        page: Номер страницы
        size: Размер страницы
    """
    logger.info(f"Getting movies with params: {search_params.dict()}")
    
    # Преобразуем параметры в фильтры для CRUD
    filters = search_params.dict(exclude={"page", "size", "sort_by", "sort_order"})
    filters = {k: v for k, v in filters.items() if v is not None}
    
    if search_params.sort_by:
        filters["sort_by"] = search_params.sort_by
        filters["sort_order"] = search_params.sort_order
    
    skip = (search_params.page - 1) * search_params.size
    
    movies = crud.get_movies(
        db=db,
        skip=skip,
        limit=search_params.size,
        filters=filters
    )
    
    total = crud.count_movies(db, filters)
    
    movie_responses = [schemas.MovieResponse.from_orm(movie) for movie in movies]
    
    paginated_response = PaginatedResponse[schemas.MovieResponse](
        items=movie_responses,
        total=total,
        page=search_params.page,
        size=search_params.size
    )
    
    return SuccessResponse[PaginatedResponse[schemas.MovieResponse]](
        message="Movies retrieved successfully",
        data=paginated_response
    )


@app.get("/api/v1/movies/{movie_id}", response_model=SuccessResponse[schemas.MovieDetailResponse])
async def get_movie(
    movie_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Получение детальной информации о фильме.
    
    Args:
        movie_id: UUID фильма
    """
    logger.info(f"Getting movie: {movie_id}")
    
    movie = crud.get_movie(db, movie_id)
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Movie with id {movie_id} not found"
        )
    
    # Получаем детальную информацию
    movie_detail = schemas.MovieDetailResponse.from_orm(movie)
    
    # Добавляем сезоны если это сериал
    if movie.content_type == schemas.ContentType.SERIES:
        movie_detail.seasons = [
            schemas.SeasonResponse.from_orm(season) 
            for season in movie.seasons
        ]
    
    return SuccessResponse[schemas.MovieDetailResponse](
        message="Movie retrieved successfully",
        data=movie_detail
    )


@app.post("/api/v1/movies", response_model=SuccessResponse[schemas.MovieResponse])
async def create_movie(
    movie: schemas.MovieCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    """
    Создание нового фильма.
    
    Requires:
        Администратор
        
    Args:
        movie: Данные для создания фильма
    """
    logger.info(f"Creating movie: {movie.title}")
    
    db_movie = crud.create_movie(
        db=db,
        movie=movie,
        user_id=UUID(current_user["id"]) if current_user else None
    )
    
    return SuccessResponse[schemas.MovieResponse](
        message="Movie created successfully",
        data=schemas.MovieResponse.from_orm(db_movie)
    )


@app.put("/api/v1/movies/{movie_id}", response_model=SuccessResponse[schemas.MovieResponse])
async def update_movie(
    movie_id: UUID,
    movie_update: schemas.MovieUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    """
    Обновление фильма.
    
    Requires:
        Администратор
        
    Args:
        movie_id: UUID фильма
        movie_update: Данные для обновления
    """
    logger.info(f"Updating movie: {movie_id}")
    
    db_movie = crud.update_movie(
        db=db,
        movie_id=movie_id,
        movie_update=movie_update,
        user_id=UUID(current_user["id"]) if current_user else None
    )
    
    return SuccessResponse[schemas.MovieResponse](
        message="Movie updated successfully",
        data=schemas.MovieResponse.from_orm(db_movie)
    )


@app.delete("/api/v1/movies/{movie_id}", response_model=SuccessResponse)
async def delete_movie(
    movie_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    """
    Удаление фильма (мягкое удаление).
    
    Requires:
        Администратор
        
    Args:
        movie_id: UUID фильма для удаления
    """
    logger.info(f"Deleting movie: {movie_id}")
    
    crud.delete_movie(
        db=db,
        movie_id=movie_id,
        user_id=UUID(current_user["id"]) if current_user else None
    )
    
    return SuccessResponse(
        message="Movie deleted successfully"
    )


@app.get("/api/v1/movies/popular", response_model=SuccessResponse[List[schemas.MovieResponse]])
async def get_popular_movies(
    limit: int = Query(10, ge=1, le=50),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """
    Получение популярных фильмов.
    
    Query Parameters:
        limit: Количество фильмов
        days: За какой период (в днях)
    """
    logger.info(f"Getting popular movies (limit: {limit}, days: {days})")
    
    movies = crud.get_popular_movies(db, limit=limit, days=days)
    
    return SuccessResponse[List[schemas.MovieResponse]](
        message="Popular movies retrieved",
        data=[schemas.MovieResponse.from_orm(movie) for movie in movies]
    )


@app.get("/api/v1/movies/recommended", response_model=SuccessResponse[List[schemas.MovieResponse]])
async def get_recommended_movies(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Получение рекомендованных фильмов.
    
    Requires:
        Аутентификация
        
    Query Parameters:
        limit: Количество фильмов
    """
    logger.info(f"Getting recommended movies for user {current_user['id']}")
    
    movies = crud.get_recommended_movies(
        db=db,
        user_id=UUID(current_user["id"]),
        limit=limit
    )
    
    return SuccessResponse[List[schemas.MovieResponse]](
        message="Recommended movies retrieved",
        data=[schemas.MovieResponse.from_orm(movie) for movie in movies]
    )


# ====== Genres endpoints ======

@app.get("/api/v1/genres", response_model=SuccessResponse[PaginatedResponse[schemas.GenreResponse]])
async def get_genres(
    pagination: dict = Depends(get_pagination_params),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Получение списка жанров.
    
    Query Parameters:
        page: Номер страницы
        size: Размер страницы
        is_active: Фильтр по активности
    """
    logger.info(f"Getting genres (page: {pagination['page']}, size: {pagination['size']})")
    
    filters = {}
    if is_active is not None:
        filters["is_active"] = is_active
    
    genres = crud.get_genres(
        db=db,
        skip=pagination["skip"],
        limit=pagination["size"],
        filters=filters
    )
    
    total = db.query(models.Genre).count()
    
    genre_responses = [schemas.GenreResponse.from_orm(genre) for genre in genres]
    
    paginated_response = PaginatedResponse[schemas.GenreResponse](
        items=genre_responses,
        total=total,
        page=pagination["page"],
        size=pagination["size"]
    )
    
    return SuccessResponse[PaginatedResponse[schemas.GenreResponse]](
        message="Genres retrieved successfully",
        data=paginated_response
    )


@app.get("/api/v1/genres/{genre_id}", response_model=SuccessResponse[schemas.GenreResponse])
async def get_genre(
    genre_id: int,
    db: Session = Depends(get_db)
):
    """
    Получение информации о жанре.
    
    Args:
        genre_id: ID жанра
    """
    logger.info(f"Getting genre: {genre_id}")
    
    genre = crud.get_genre(db, genre_id)
    if not genre:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Genre with id {genre_id} not found"
        )
    
    return SuccessResponse[schemas.GenreResponse](
        message="Genre retrieved successfully",
        data=schemas.GenreResponse.from_orm(genre)
    )


@app.post("/api/v1/genres", response_model=SuccessResponse[schemas.GenreResponse])
async def create_genre(
    genre: schemas.GenreCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    """
    Создание нового жанра.
    
    Requires:
        Администратор
        
    Args:
        genre: Данные для создания жанра
    """
    logger.info(f"Creating genre: {genre.name}")
    
    db_genre = crud.create_genre(
        db=db,
        genre=genre,
        user_id=UUID(current_user["id"]) if current_user else None
    )
    
    return SuccessResponse[schemas.GenreResponse](
        message="Genre created successfully",
        data=schemas.GenreResponse.from_orm(db_genre)
    )


@app.put("/api/v1/genres/{genre_id}", response_model=SuccessResponse[schemas.GenreResponse])
async def update_genre(
    genre_id: int,
    genre_update: schemas.GenreUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    """
    Обновление жанра.
    
    Requires:
        Администратор
        
    Args:
        genre_id: ID жанра
        genre_update: Данные для обновления
    """
    logger.info(f"Updating genre: {genre_id}")
    
    db_genre = crud.update_genre(
        db=db,
        genre_id=genre_id,
        genre_update=genre_update,
        user_id=UUID(current_user["id"]) if current_user else None
    )
    
    return SuccessResponse[schemas.GenreResponse](
        message="Genre updated successfully",
        data=schemas.GenreResponse.from_orm(db_genre)
    )


@app.get("/api/v1/genres/slug/{slug}", response_model=SuccessResponse[schemas.GenreResponse])
async def get_genre_by_slug(
    slug: str,
    db: Session = Depends(get_db)
):
    """
    Получение информации о жанре по slug.
    
    Args:
        slug: Уникальный идентификатор жанра
    """
    logger.info(f"Getting genre by slug: {slug}")
    
    genre = crud.get_genre_by_slug(db, slug)
    if not genre:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Genre with slug '{slug}' not found"
        )
    
    return SuccessResponse[schemas.GenreResponse](
        message="Genre retrieved successfully",
        data=schemas.GenreResponse.from_orm(genre)
    )


# ====== Persons endpoints ======

@app.get("/api/v1/persons", response_model=SuccessResponse[PaginatedResponse[schemas.PersonResponse]])
async def get_persons(
    pagination: dict = Depends(get_pagination_params),
    query: Optional[str] = Query(None),
    role: Optional[str] = Query(None, regex="^(actor|director|writer)$"),
    db: Session = Depends(get_db)
):
    """
    Получение списка людей (актеров, режиссеров, сценаристов).
    
    Query Parameters:
        page: Номер страницы
        size: Размер страницы
        query: Поисковый запрос (имя)
        role: Роль (actor, director, writer)
    """
    logger.info(f"Getting persons (query: {query}, role: {role})")
    
    filters = {}
    if query:
        filters["query"] = query
    if role:
        filters["role"] = role
    
    persons = crud.get_persons(
        db=db,
        skip=pagination["skip"],
        limit=pagination["size"],
        filters=filters
    )
    
    total = db.query(models.Person).count()
    
    person_responses = [schemas.PersonResponse.from_orm(person) for person in persons]
    
    paginated_response = PaginatedResponse[schemas.PersonResponse](
        items=person_responses,
        total=total,
        page=pagination["page"],
        size=pagination["size"]
    )
    
    return SuccessResponse[PaginatedResponse[schemas.PersonResponse]](
        message="Persons retrieved successfully",
        data=paginated_response
    )


@app.get("/api/v1/persons/{person_id}", response_model=SuccessResponse[schemas.PersonResponse])
async def get_person(
    person_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Получение информации о человеке.
    
    Args:
        person_id: UUID человека
    """
    logger.info(f"Getting person: {person_id}")
    
    person = crud.get_person(db, person_id)
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Person with id {person_id} not found"
        )
    
    return SuccessResponse[schemas.PersonResponse](
        message="Person retrieved successfully",
        data=schemas.PersonResponse.from_orm(person)
    )


@app.post("/api/v1/persons", response_model=SuccessResponse[schemas.PersonResponse])
async def create_person(
    person: schemas.PersonCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    """
    Создание нового человека.
    
    Requires:
        Администратор
        
    Args:
        person: Данные для создания человека
    """
    logger.info(f"Creating person: {person.full_name}")
    
    db_person = crud.create_person(
        db=db,
        person=person,
        user_id=UUID(current_user["id"]) if current_user else None
    )
    
    return SuccessResponse[schemas.PersonResponse](
        message="Person created successfully",
        data=schemas.PersonResponse.from_orm(db_person)
    )


@app.put("/api/v1/persons/{person_id}", response_model=SuccessResponse[schemas.PersonResponse])
async def update_person(
    person_id: UUID,
    person_update: schemas.PersonUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    """
    Обновление информации о человеке.
    
    Requires:
        Администратор
        
    Args:
        person_id: UUID человека
        person_update: Данные для обновления
    """
    logger.info(f"Updating person: {person_id}")
    
    db_person = crud.update_person(
        db=db,
        person_id=person_id,
        person_update=person_update,
        user_id=UUID(current_user["id"]) if current_user else None
    )
    
    return SuccessResponse[schemas.PersonResponse](
        message="Person updated successfully",
        data=schemas.PersonResponse.from_orm(db_person)
    )


# ====== Reviews endpoints ======

@app.post("/api/v1/reviews", response_model=SuccessResponse[schemas.ReviewResponse])
async def create_review(
    review: schemas.ReviewCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Создание отзыва на фильм.
    
    Requires:
        Аутентификация
        
    Args:
        review: Данные отзыва
    """
    logger.info(f"Creating review for movie {review.movie_id} by user {current_user['id']}")
    
    db_review = crud.create_review(
        db=db,
        review=review,
        user_id=UUID(current_user["id"]),
        ip_address=request.client.host if request.client else None
    )
    
    return SuccessResponse[schemas.ReviewResponse](
        message="Review created successfully",
        data=schemas.ReviewResponse.from_orm(db_review)
    )


@app.get("/api/v1/movies/{movie_id}/reviews", response_model=SuccessResponse[PaginatedResponse[schemas.ReviewResponse]])
async def get_movie_reviews(
    movie_id: UUID,
    pagination: dict = Depends(get_pagination_params),
    db: Session = Depends(get_db)
):
    """
    Получение отзывов на фильм.
    
    Args:
        movie_id: UUID фильма
        page: Номер страницы
        size: Размер страницы
    """
    logger.info(f"Getting reviews for movie: {movie_id}")
    
    # Проверяем существование фильма
    movie = crud.get_movie(db, movie_id)
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Movie with id {movie_id} not found"
        )
    
    reviews = db.query(models.Review).filter(
        models.Review.movie_id == movie_id,
        models.Review.is_active == True
    ).order_by(
        desc(models.Review.created_at)
    ).offset(pagination["skip"]).limit(pagination["size"]).all()
    
    total = db.query(models.Review).filter(
        models.Review.movie_id == movie_id,
        models.Review.is_active == True
    ).count()
    
    review_responses = [schemas.ReviewResponse.from_orm(review) for review in reviews]
    
    paginated_response = PaginatedResponse[schemas.ReviewResponse](
        items=review_responses,
        total=total,
        page=pagination["page"],
        size=pagination["size"]
    )
    
    return SuccessResponse[PaginatedResponse[schemas.ReviewResponse]](
        message="Reviews retrieved successfully",
        data=paginated_response
    )


# ====== Watchlist endpoints ======

@app.post("/api/v1/watchlist", response_model=SuccessResponse[schemas.WatchlistResponse])
async def add_to_watchlist(
    watchlist_item: schemas.WatchlistCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Добавление фильма в список просмотра.
    
    Requires:
        Аутентификация
        
    Args:
        watchlist_item: Данные для добавления
    """
    logger.info(f"Adding movie {watchlist_item.movie_id} to watchlist for user {current_user['id']}")
    
    db_watchlist = crud.add_to_watchlist(
        db=db,
        user_id=UUID(current_user["id"]),
        watchlist_item=watchlist_item
    )
    
    return SuccessResponse[schemas.WatchlistResponse](
        message="Movie added to watchlist successfully",
        data=schemas.WatchlistResponse.from_orm(db_watchlist)
    )


@app.get("/api/v1/watchlist", response_model=SuccessResponse[List[schemas.WatchlistResponse]])
async def get_watchlist(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Получение списка просмотра пользователя.
    
    Requires:
        Аутентификация
        
    Query Parameters:
        skip: Пропустить первые N записей
        limit: Максимальное количество записей
    """
    logger.info(f"Getting watchlist for user {current_user['id']}")
    
    watchlist = crud.get_watchlist(
        db=db,
        user_id=UUID(current_user["id"]),
        skip=skip,
        limit=limit
    )
    
    return SuccessResponse[List[schemas.WatchlistResponse]](
        message="Watchlist retrieved successfully",
        data=[schemas.WatchlistResponse.from_orm(item) for item in watchlist]
    )


@app.delete("/api/v1/watchlist/{movie_id}", response_model=SuccessResponse)
async def remove_from_watchlist(
    movie_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Удаление фильма из списка просмотра.
    
    Requires:
        Аутентификация
        
    Args:
        movie_id: UUID фильма для удаления
    """
    logger.info(f"Removing movie {movie_id} from watchlist for user {current_user['id']}")
    
    crud.remove_from_watchlist(
        db=db,
        user_id=UUID(current_user["id"]),
        movie_id=movie_id
    )
    
    return SuccessResponse(
        message="Movie removed from watchlist successfully"
    )


# ====== Statistics endpoints ======

@app.get("/api/v1/stats/movies/{movie_id}", response_model=SuccessResponse)
async def get_movie_stats(
    movie_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Получение статистики фильма.
    
    Args:
        movie_id: UUID фильма
    """
    logger.info(f"Getting stats for movie: {movie_id}")
    
    stats = crud.get_movie_stats(db, movie_id)
    
    return SuccessResponse(
        message="Movie statistics retrieved",
        data=stats
    )


@app.get("/api/v1/stats/genres", response_model=SuccessResponse)
async def get_genre_stats(db: Session = Depends(get_db)):
    """
    Получение статистики по жанрам.
    """
    logger.info("Getting genre statistics")
    
    stats = crud.get_genre_stats(db)
    
    return SuccessResponse(
        message="Genre statistics retrieved",
        data=stats
    )


# ====== Seasons and Episodes endpoints (для сериалов) ======

@app.post("/api/v1/movies/{movie_id}/seasons", response_model=SuccessResponse[schemas.SeasonResponse])
async def create_season(
    movie_id: UUID,
    season: schemas.SeasonCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    """
    Создание сезона для сериала.
    
    Requires:
        Администратор
        
    Args:
        movie_id: UUID фильма (сериала)
        season: Данные для создания сезона
    """
    logger.info(f"Creating season for movie {movie_id}")
    
    # Проверяем что фильм является сериалом
    movie = crud.get_movie(db, movie_id)
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Movie with id {movie_id} not found"
        )
    
    if movie.content_type != schemas.ContentType.SERIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only add seasons to series"
        )
    
    db_season = crud.create_season(
        db=db,
        movie_id=movie_id,
        season=season,
        user_id=UUID(current_user["id"]) if current_user else None
    )
    
    return SuccessResponse[schemas.SeasonResponse](
        message="Season created successfully",
        data=schemas.SeasonResponse.from_orm(db_season)
    )


@app.post("/api/v1/seasons/{season_id}/episodes", response_model=SuccessResponse[schemas.EpisodeResponse])
async def create_episode(
    season_id: UUID,
    episode: schemas.EpisodeCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    """
    Создание серии для сезона.
    
    Requires:
        Администратор
        
    Args:
        season_id: UUID сезона
        episode: Данные для создания серии
    """
    logger.info(f"Creating episode for season {season_id}")
    
    db_episode = crud.create_episode(
        db=db,
        season_id=season_id,
        episode=episode,
        user_id=UUID(current_user["id"]) if current_user else None
    )
    
    return SuccessResponse[schemas.EpisodeResponse](
        message="Episode created successfully",
        data=schemas.EpisodeResponse.from_orm(db_episode)
    )


# ====== Event handlers ======

@app.on_event("startup")
async def startup_event():
    """Действия при запуске сервиса."""
    logger.info("Starting Catalog Service...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Database URL: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else settings.DATABASE_URL}")


@app.on_event("shutdown")
async def shutdown_event():
    """Действия при остановке сервиса."""
    logger.info("Shutting down Catalog Service...")