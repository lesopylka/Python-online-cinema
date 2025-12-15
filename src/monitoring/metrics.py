"""
Метрики Prometheus для мониторинга системы.
"""

from prometheus_client import Counter, Histogram, Gauge, generate_latest
from prometheus_client.openmetrics.exposition import CONTENT_TYPE_LATEST
from prometheus_client.registry import REGISTRY
from fastapi import FastAPI, Request, Response
from typing import Callable
import time
import logging

logger = logging.getLogger(__name__)

# ====== HTTP метрики ======

# Общее количество HTTP запросов
HTTP_REQUESTS_TOTAL = Counter(
    'http_requests_total',
    'Total number of HTTP requests',
    ['method', 'endpoint', 'status']
)

# Время выполнения HTTP запросов
HTTP_REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0)
)

# Активные HTTP запросы
HTTP_REQUESTS_IN_PROGRESS = Gauge(
    'http_requests_in_progress',
    'Current number of HTTP requests in progress',
    ['method', 'endpoint']
)

# Размеры HTTP запросов
HTTP_REQUEST_SIZE = Histogram(
    'http_request_size_bytes',
    'HTTP request size in bytes',
    ['method', 'endpoint'],
    buckets=(100, 1000, 10000, 100000, 1000000)
)

# Размеры HTTP ответов
HTTP_RESPONSE_SIZE = Histogram(
    'http_response_size_bytes',
    'HTTP response size in bytes',
    ['method', 'endpoint'],
    buckets=(100, 1000, 10000, 100000, 1000000)
)

# ====== Бизнес метрики ======

# События пользователей
USER_EVENTS_TOTAL = Counter(
    'user_events_total',
    'Total number of user events',
    ['event_type', 'user_type']
)

# Просмотры фильмов
MOVIE_VIEWS_TOTAL = Counter(
    'movie_views_total',
    'Total number of movie views',
    ['movie_id', 'genre']
)

# Поисковые запросы
SEARCH_QUERIES_TOTAL = Counter(
    'search_queries_total',
    'Total number of search queries',
    ['query_type', 'result_count']
)

# Ошибки при поиске
SEARCH_ERRORS_TOTAL = Counter(
    'search_errors_total',
    'Total number of search errors',
    ['error_type']
)

# ====== Системные метрики ======

# Состояние сервисов
SERVICE_STATUS = Gauge(
    'service_status',
    'Service status (1=healthy, 0=unhealthy)',
    ['service_name']
)

# Время ответа сервисов
SERVICE_RESPONSE_TIME = Histogram(
    'service_response_time_seconds',
    'Service response time in seconds',
    ['service_name'],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0)
)

# Ошибки сервисов
SERVICE_ERRORS_TOTAL = Counter(
    'service_errors_total',
    'Total number of service errors',
    ['service_name', 'error_type']
)

# ====== БД метрики ======

# Запросы к базе данных
DATABASE_QUERIES_TOTAL = Counter(
    'database_queries_total',
    'Total number of database queries',
    ['query_type', 'table']
)

# Время выполнения запросов
DATABASE_QUERY_DURATION = Histogram(
    'database_query_duration_seconds',
    'Database query duration in seconds',
    ['query_type', 'table'],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0)
)

# Ошибки базы данных
DATABASE_ERRORS_TOTAL = Counter(
    'database_errors_total',
    'Total number of database errors',
    ['error_type']
)

# ====== Kafka метрики ======

# Сообщения Kafka
KAFKA_MESSAGES_TOTAL = Counter(
    'kafka_messages_total',
    'Total number of Kafka messages',
    ['topic', 'status']
)

# Время обработки сообщений
KAFKA_PROCESSING_TIME = Histogram(
    'kafka_processing_time_seconds',
    'Kafka message processing time in seconds',
    ['topic'],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0)
)

# Лаг обработки сообщений
KAFKA_CONSUMER_LAG = Gauge(
    'kafka_consumer_lag',
    'Kafka consumer lag in messages',
    ['topic', 'partition', 'consumer_group']
)


def setup_metrics(app: FastAPI):
    """
    Настройка метрик для FastAPI приложения.
    
    Args:
        app: FastAPI приложение
    """
    
    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next: Callable):
        """
        Middleware для сбора метрик HTTP запросов.
        """
        
        # Определяем endpoint
        endpoint = request.url.path
        
        # Увеличиваем счетчик активных запросов
        HTTP_REQUESTS_IN_PROGRESS.labels(
            method=request.method,
            endpoint=endpoint
        ).inc()
        
        # Измеряем время выполнения
        start_time = time.time()
        
        # Измеряем размер запроса
        request_size = 0
        if request.method in ["POST", "PUT", "PATCH"]:
            body = await request.body()
            request_size = len(body)
        
        HTTP_REQUEST_SIZE.labels(
            method=request.method,
            endpoint=endpoint
        ).observe(request_size)
        
        try:
            # Выполняем запрос
            response = await call_next(request)
            
            # Время выполнения
            duration = time.time() - start_time
            
            # Регистрируем успешный запрос
            HTTP_REQUESTS_TOTAL.labels(
                method=request.method,
                endpoint=endpoint,
                status=response.status_code
            ).inc()
            
            HTTP_REQUEST_DURATION.labels(
                method=request.method,
                endpoint=endpoint
            ).observe(duration)
            
            # Размер ответа
            if hasattr(response, 'body'):
                response_size = len(response.body)
                HTTP_RESPONSE_SIZE.labels(
                    method=request.method,
                    endpoint=endpoint
                ).observe(response_size)
            
            logger.debug(
                f"Request metrics: {request.method} {endpoint} "
                f"status={response.status_code} duration={duration:.3f}s"
            )
            
            return response
            
        except Exception as e:
            # Время выполнения при ошибке
            duration = time.time() - start_time
            
            # Регистрируем ошибку
            HTTP_REQUESTS_TOTAL.labels(
                method=request.method,
                endpoint=endpoint,
                status=500
            ).inc()
            
            HTTP_REQUEST_DURATION.labels(
                method=request.method,
                endpoint=endpoint
            ).observe(duration)
            
            logger.error(
                f"Request failed: {request.method} {endpoint} "
                f"duration={duration:.3f}s error={str(e)}"
            )
            
            raise
            
        finally:
            # Уменьшаем счетчик активных запросов
            HTTP_REQUESTS_IN_PROGRESS.labels(
                method=request.method,
                endpoint=endpoint
            ).dec()
    
    @app.get("/metrics")
    async def metrics_endpoint():
        """
        Endpoint для получения метрик в формате Prometheus.
        """
        return Response(
            content=generate_latest(REGISTRY),
            media_type=CONTENT_TYPE_LATEST
        )


def record_user_event(event_type: str, user_type: str = "regular"):
    """
    Запись события пользователя.
    
    Args:
        event_type: Тип события
        user_type: Тип пользователя
    """
    USER_EVENTS_TOTAL.labels(
        event_type=event_type,
        user_type=user_type
    ).inc()


def record_movie_view(movie_id: str, genre: str = "unknown"):
    """
    Запись просмотра фильма.
    
    Args:
        movie_id: ID фильма
        genre: Жанр фильма
    """
    MOVIE_VIEWS_TOTAL.labels(
        movie_id=movie_id,
        genre=genre
    ).inc()


def record_search_query(query_type: str, result_count: int = 0):
    """
    Запись поискового запроса.
    
    Args:
        query_type: Тип запроса
        result_count: Количество результатов
    """
    SEARCH_QUERIES_TOTAL.labels(
        query_type=query_type,
        result_count=str(result_count)
    ).inc()


def record_service_call(
    service_name: str,
    duration: float,
    success: bool = True,
    error_type: str = None
):
    """
    Запись вызова сервиса.
    
    Args:
        service_name: Название сервиса
        duration: Время выполнения
        success: Успешность вызова
        error_type: Тип ошибки (если не успешно)
    """
    SERVICE_RESPONSE_TIME.labels(
        service_name=service_name
    ).observe(duration)
    
    if not success and error_type:
        SERVICE_ERRORS_TOTAL.labels(
            service_name=service_name,
            error_type=error_type
        ).inc()


def record_database_query(
    query_type: str,
    table: str,
    duration: float,
    success: bool = True
):
    """
    Запись запроса к базе данных.
    
    Args:
        query_type: Тип запроса
        table: Таблица
        duration: Время выполнения
        success: Успешность запроса
    """
    DATABASE_QUERIES_TOTAL.labels(
        query_type=query_type,
        table=table
    ).inc()
    
    DATABASE_QUERY_DURATION.labels(
        query_type=query_type,
        table=table
    ).observe(duration)
    
    if not success:
        DATABASE_ERRORS_TOTAL.labels(
            error_type=query_type
        ).inc()


def record_kafka_message(
    topic: str,
    status: str = "sent",
    duration: float = None
):
    """
    Запись сообщения Kafka.
    
    Args:
        topic: Топик
        status: Статус (sent, consumed, error)
        duration: Время обработки
    """
    KAFKA_MESSAGES_TOTAL.labels(
        topic=topic,
        status=status
    ).inc()
    
    if duration is not None:
        KAFKA_PROCESSING_TIME.labels(
            topic=topic
        ).observe(duration)


def set_service_status(service_name: str, healthy: bool):
    """
    Установка статуса сервиса.
    
    Args:
        service_name: Название сервиса
        healthy: Статус здоровья
    """
    value = 1 if healthy else 0
    SERVICE_STATUS.labels(
        service_name=service_name
    ).set(value)