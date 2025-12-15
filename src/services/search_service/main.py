"""
Основной файл Search Service.
"""

import logging
import asyncio
import json
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Request, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from kafka import KafkaConsumer
from threading import Thread

from src.config.settings import settings
from src.shared.logging import setup_logging
from src.shared.exceptions import ServiceException
from src.shared.schemas import (
    SuccessResponse, ErrorResponse, HealthCheck, Status
)
from src.monitoring.metrics import setup_metrics
from src.monitoring.tracing import setup_tracing
from src.shared.kafka_producer import send_kafka_message
from src.monitoring.logging_config import request_logger

from . import schemas
from .es_client import es_client

# Настройка логирования
setup_logging("search-service")
logger = logging.getLogger(__name__)

# Создание приложения
app = FastAPI(
    title="Search Service",
    description="Сервис полнотекстового поиска фильмов с использованием Elasticsearch",
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


# ====== Вспомогательные функции ======

async def process_movie_index_event(event_data: dict):
    """
    Обработка события индексации фильма из Kafka.
    
    Args:
        event_data: Данные события
    """
    try:
        action = event_data.get("action")
        movie_id = event_data.get("movie_id")
        
        if not action or not movie_id:
            logger.warning(f"Invalid movie index event: {event_data}")
            return
        
        if action == "index":
            # В реальном приложении здесь был бы запрос к Catalog Service
            # для получения полных данных фильма
            logger.info(f"Movie index requested: {movie_id}")
            
        elif action == "update":
            # Обновление фильма в индексе
            update_data = event_data.get("movie_data", {})
            if update_data:
                await es_client.update_movie(movie_id, update_data)
                logger.info(f"Movie updated in index: {movie_id}")
            
        elif action == "delete":
            # Удаление фильма из индекса
            await es_client.delete_movie(movie_id)
            logger.info(f"Movie deleted from index: {movie_id}")
        
    except Exception as e:
        logger.error(f"Failed to process movie index event: {e}")


def kafka_consumer_thread():
    """
    Поток для потребления событий из Kafka.
    """
    consumer = KafkaConsumer(
        settings.KAFKA_TOPIC_MOVIE_INDEX,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS.split(','),
        auto_offset_reset='earliest',
        enable_auto_commit=True,
        group_id='search-service-group',
        value_deserializer=lambda x: json.loads(x.decode('utf-8')) if x else None
    )
    
    logger.info("Kafka consumer started for movie index events")
    
    for message in consumer:
        try:
            if message.value:
                # Запускаем асинхронную обработку в новом event loop
                asyncio.run(process_movie_index_event(message.value))
                
        except Exception as e:
            logger.error(f"Error processing Kafka message: {e}")


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
        status_code=500,
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
        "message": "Search Service",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    Проверяет подключение к Elasticsearch.
    """
    dependencies_status = {}
    
    # Проверка Elasticsearch
    try:
        es_healthy = await es_client.health_check()
        dependencies_status["elasticsearch"] = "healthy" if es_healthy else "unhealthy"
    except Exception as e:
        logger.error(f"Elasticsearch health check failed: {e}")
        dependencies_status["elasticsearch"] = "unreachable"
    
    # Проверка Kafka
    dependencies_status["kafka"] = "unknown"  # Упрощённая проверка
    
    return HealthCheck(
        status="healthy" if dependencies_status.get("elasticsearch") == "healthy" else "degraded",
        service="search-service",
        version="1.0.0",
        dependencies=dependencies_status
    )


# ====== Search endpoints ======

@app.get("/api/v1/search", response_model=SuccessResponse[schemas.SearchResponse])
async def search_movies(
    query: Optional[str] = Query(None, min_length=1, max_length=200),
    genre_ids: Optional[str] = Query(None),  # Список ID через запятую
    content_type: Optional[str] = Query(None, regex="^(movie|series|documentary|short|animation)$"),
    min_rating: Optional[float] = Query(None, ge=0.0, le=10.0),
    max_rating: Optional[float] = Query(None, ge=0.0, le=10.0),
    year_from: Optional[int] = Query(None, ge=1888, le=2100),
    year_to: Optional[int] = Query(None, ge=1888, le=2100),
    country: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    age_rating: Optional[str] = Query(None, regex="^(G|PG|PG-13|R|NC-17)$"),
    sort_by: schemas.SearchSortField = Query(schemas.SearchSortField.RELEVANCE),
    sort_order: schemas.SearchSortOrder = Query(schemas.SearchSortOrder.DESC),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    request: Request = None
):
    """
    Поиск фильмов по тексту с фильтрами.
    
    Query Parameters:
        query: Поисковый запрос
        genre_ids: Список ID жанров через запятую
        content_type: Тип контента
        min_rating: Минимальный рейтинг
        max_rating: Максимальный рейтинг
        year_from: Год от
        year_to: Год до
        country: Страна
        language: Язык
        age_rating: Возрастной рейтинг
        sort_by: Поле сортировки
        sort_order: Порядок сортировки
        page: Номер страницы
        size: Размер страницы
    """
    start_time = datetime.now()
    
    try:
        # Подготавливаем фильтры
        filters = {}
        
        if genre_ids:
            try:
                filters["genre_ids"] = [int(gid.strip()) for gid in genre_ids.split(",")]
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid genre_ids format")
        
        if content_type:
            filters["content_type"] = content_type
        
        if min_rating is not None:
            filters["min_rating"] = min_rating
        
        if max_rating is not None:
            filters["max_rating"] = max_rating
        
        if year_from is not None:
            filters["year_from"] = year_from
        
        if year_to is not None:
            filters["year_to"] = year_to
        
        if country:
            filters["country"] = country
        
        if language:
            filters["language"] = language
        
        if age_rating:
            filters["age_rating"] = age_rating
        
        # Определяем поле для сортировки в Elasticsearch
        es_sort_by = None
        if sort_by == schemas.SearchSortField.TITLE:
            es_sort_by = "title.keyword"
        elif sort_by == schemas.SearchSortField.RATING:
            es_sort_by = "rating"
        elif sort_by == schemas.SearchSortField.RELEASE_YEAR:
            es_sort_by = "release_year"
        elif sort_by == schemas.SearchSortField.CREATED_AT:
            es_sort_by = "created_at"
        # Для relevance не указываем сортировку - будет использоваться _score
        
        # Выполняем поиск
        results, total = await es_client.search_movies(
            query=query or "",
            filters=filters,
            sort_by=es_sort_by,
            sort_order=sort_order.value,
            page=page,
            size=size
        )
        
        # Преобразуем результаты
        search_results = []
        for result in results:
            try:
                search_result = schemas.SearchResult(
                    id=result.get("id", ""),
                    title=result.get("title", ""),
                    original_title=result.get("original_title"),
                    description=result.get("description"),
                    content_type=result.get("content_type", "movie"),
                    release_year=result.get("release_year"),
                    duration_minutes=result.get("duration_minutes"),
                    rating=result.get("rating", 0.0),
                    age_rating=result.get("age_rating", "PG-13"),
                    poster_url=result.get("poster_url"),
                    backdrop_url=result.get("backdrop_url"),
                    country=result.get("country"),
                    language=result.get("language"),
                    genres=result.get("genres", []),
                    actors=result.get("actors", []),
                    directors=result.get("directors", []),
                    created_at=result.get("created_at", datetime.utcnow().isoformat()),
                    updated_at=result.get("updated_at"),
                    score=result.get("_score", 0.0)
                )
                search_results.append(search_result)
            except Exception as e:
                logger.warning(f"Failed to parse search result: {e}")
                continue
        
        # Время выполнения
        took = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # Отправляем событие аналитики
        try:
            # Получаем user_id из заголовков если есть
            user_id = None
            auth_header = request.headers.get("Authorization") if request else None
            if auth_header and auth_header.startswith("Bearer "):
                # В реальном приложении здесь была бы расшифровка JWT токена
                pass
            
            send_kafka_message(
                topic="search_analytics",
                value={
                    "query": query or "",
                    "filters": filters,
                    "results_count": len(search_results),
                    "user_id": user_id,
                    "session_id": request.cookies.get("session_id") if request else None,
                    "timestamp": datetime.utcnow().isoformat(),
                    "service": "search-service"
                }
            )
        except Exception as e:
            logger.warning(f"Failed to send search analytics: {e}")
        
        # Формируем ответ
        search_response = schemas.SearchResponse(
            query=query,
            results=search_results,
            total=total,
            page=page,
            size=size,
            pages=(total + size - 1) // size,
            took=took,
            filters=filters if filters else None
        )
        
        logger.info(f"Search completed: query='{query}', results={len(search_results)}, took={took}ms")
        
        return SuccessResponse[schemas.SearchResponse](
            message="Search completed successfully",
            data=search_response
        )
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail="Search failed")


@app.get("/api/v1/search/autocomplete", response_model=SuccessResponse[schemas.AutocompleteResponse])
async def autocomplete(
    query: str = Query(..., min_length=1, max_length=100),
    size: int = Query(10, ge=1, le=20),
    content_type: Optional[str] = Query(None, regex="^(movie|series|documentary|short|animation)$")
):
    """
    Автодополнение поисковых запросов.
    
    Query Parameters:
        query: Часть запроса
        size: Количество результатов
        content_type: Ограничение по типу контента
    """
    start_time = datetime.now()
    
    try:
        suggestions = await es_client.autocomplete(
            query=query,
            size=size,
            content_type=content_type
        )
        
        # Преобразуем результаты
        autocomplete_results = []
        for suggestion in suggestions:
            result = schemas.AutocompleteResult(
                text=suggestion.get("text", ""),
                score=suggestion.get("score", 0.0),
                source=suggestion.get("source")
            )
            autocomplete_results.append(result)
        
        # Время выполнения
        took = int((datetime.now() - start_time).total_seconds() * 1000)
        
        autocomplete_response = schemas.AutocompleteResponse(
            query=query,
            suggestions=autocomplete_results,
            took=took
        )
        
        logger.debug(f"Autocomplete: query='{query}', suggestions={len(autocomplete_results)}")
        
        return SuccessResponse[schemas.AutocompleteResponse](
            message="Autocomplete completed successfully",
            data=autocomplete_response
        )
        
    except Exception as e:
        logger.error(f"Autocomplete failed: {e}")
        raise HTTPException(status_code=500, detail="Autocomplete failed")


@app.get("/api/v1/search/similar/{movie_id}", response_model=SuccessResponse[schemas.SimilarMoviesResponse])
async def search_similar_movies(
    movie_id: str,
    size: int = Query(10, ge=1, le=20)
):
    """
    Поиск похожих фильмов.
    
    Args:
        movie_id: ID фильма
        size: Количество результатов
    """
    start_time = datetime.now()
    
    try:
        similar_movies = await es_client.search_similar(
            movie_id=movie_id,
            size=size
        )
        
        # Преобразуем результаты
        search_results = []
        for result in similar_movies:
            try:
                search_result = schemas.SearchResult(
                    id=result.get("id", ""),
                    title=result.get("title", ""),
                    original_title=result.get("original_title"),
                    description=result.get("description"),
                    content_type=result.get("content_type", "movie"),
                    release_year=result.get("release_year"),
                    duration_minutes=result.get("duration_minutes"),
                    rating=result.get("rating", 0.0),
                    age_rating=result.get("age_rating", "PG-13"),
                    poster_url=result.get("poster_url"),
                    backdrop_url=result.get("backdrop_url"),
                    country=result.get("country"),
                    language=result.get("language"),
                    genres=result.get("genres", []),
                    actors=result.get("actors", []),
                    directors=result.get("directors", []),
                    created_at=result.get("created_at", datetime.utcnow().isoformat()),
                    updated_at=result.get("updated_at"),
                    score=result.get("_score", 0.0)
                )
                search_results.append(search_result)
            except Exception as e:
                logger.warning(f"Failed to parse similar movie result: {e}")
                continue
        
        # Время выполнения
        took = int((datetime.now() - start_time).total_seconds() * 1000)
        
        similar_response = schemas.SimilarMoviesResponse(
            movie_id=movie_id,
            similar_movies=search_results,
            total=len(search_results),
            took=took
        )
        
        logger.info(f"Similar search: movie_id={movie_id}, results={len(search_results)}")
        
        return SuccessResponse[schemas.SimilarMoviesResponse](
            message="Similar movies search completed",
            data=similar_response
        )
        
    except Exception as e:
        logger.error(f"Similar search failed for movie {movie_id}: {e}")
        raise HTTPException(status_code=500, detail="Similar movies search failed")


# ====== Admin endpoints ======

@app.get("/api/v1/admin/search/stats", response_model=SuccessResponse[schemas.IndexStatsResponse])
async def get_search_stats():
    """
    Получение статистики поискового индекса.
    
    Requires:
        Администратор
    """
    try:
        stats = await es_client.get_index_stats()
        
        # Проверяем здоровье Elasticsearch
        health = await es_client.health_check()
        stats["health"] = "healthy" if health else "unhealthy"
        
        index_stats = schemas.IndexStatsResponse(**stats)
        
        return SuccessResponse[schemas.IndexStatsResponse](
            message="Search index statistics retrieved",
            data=index_stats
        )
        
    except Exception as e:
        logger.error(f"Failed to get search stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get search statistics")


@app.post("/api/v1/admin/search/reindex")
async def reindex_all_movies(background_tasks: BackgroundTasks):
    """
    Переиндексация всех фильмов.
    
    Requires:
        Администратор
        
    Note:
        В реальном приложении здесь был бы запрос к Catalog Service
        для получения всех фильмов и их индексации
    """
    logger.info("Reindex all movies requested")
    
    # В фоновом режиме запускаем переиндексацию
    background_tasks.add_task(_reindex_movies_background)
    
    return SuccessResponse(
        message="Reindexing started in background",
        data={"status": "started"}
    )


async def _reindex_movies_background():
    """
    Фоновая задача для переиндексации фильмов.
    """
    try:
        logger.info("Starting background reindexing...")
        
        # 1. Получить все фильмы из Catalog Service (в реальном приложении)
        # 2. Индексировать каждый фильм в Elasticsearch
        # 3. Логировать прогресс
        
        logger.info("Background reindexing completed")
        
    except Exception as e:
        logger.error(f"Background reindexing failed: {e}")


# ====== Event handlers ======

@app.on_event("startup")
async def startup_event():
    """Действия при запуске сервиса."""
    logger.info("Starting Search Service...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Elasticsearch URL: {settings.ELASTICSEARCH_URL}")
    
    # Создаем индекс Elasticsearch
    success = await es_client.create_index()
    if success:
        logger.info("Elasticsearch index created/verified")
    else:
        logger.error("Failed to create Elasticsearch index")
    
    # Запускаем Kafka consumer в отдельном потоке
    thread = Thread(target=kafka_consumer_thread, daemon=True)
    thread.start()
    logger.info("Kafka consumer thread started")


@app.on_event("shutdown")
async def shutdown_event():
    """Действия при остановке сервиса."""
    logger.info("Shutting down Search Service...")
    
    # Закрываем соединение с Elasticsearch
    await es_client.close()