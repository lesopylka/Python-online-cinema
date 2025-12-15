# app/monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client.registry import CollectorRegistry
from fastapi import Request, Response
import time

# Создаем собственный реестр метрик
registry = CollectorRegistry()

# Метрики активности
ACTIVITY_EVENTS_RECEIVED = Counter(
    'activity_events_received_total',
    'Total number of received activity events',
    ['client_type'],
    registry=registry
)

ACTIVITY_PROCESSING_TIME = Histogram(
    'activity_processing_seconds',
    'Time spent processing activity events',
    registry=registry
)

ACTIVITY_BATCH_SIZE = Histogram(
    'activity_batch_size',
    'Size of activity event batches',
    buckets=[1, 5, 10, 25, 50, 100, 250, 500],
    registry=registry
)

# Метрики сессий
ACTIVE_SESSIONS = Gauge(
    'active_sessions',
    'Number of active user sessions',
    registry=registry
)

SESSIONS_UPDATED = Counter(
    'sessions_updated_total',
    'Total number of session updates',
    registry=registry
)

EVENTS_STORED = Counter(
    'events_stored_total',
    'Total number of stored events',
    registry=registry
)

# Метрики стриминга
STREAM_REQUESTS = Counter(
    'stream_requests_total',
    'Total number of stream requests',
    ['endpoint'],
    registry=registry
)

STREAM_BYTES_SERVED = Counter(
    'stream_bytes_served_total',
    'Total bytes served for streaming',
    registry=registry
)

STREAM_ERRORS = Counter(
    'stream_errors_total',
    'Total number of stream errors',
    ['error_type'],
    registry=registry
)


def setup_metrics():
    """Инициализация метрик"""
    print("✅ Метрики инициализированы")


def instrument_app(app):
    """Добавление middleware для сбора метрик в FastAPI приложение"""

    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        start_time = time.time()

        try:
            response = await call_next(request)

            # Логируем метрики для запросов
            process_time = time.time() - start_time

            # Эндпоинт для метрик пропускаем
            if request.url.path != "/metrics":
                STREAM_REQUESTS.labels(
                    endpoint=request.url.path
                ).inc()

            return response

        except Exception as e:
            STREAM_ERRORS.labels(error_type="http_error").inc()
            raise

    # Добавляем endpoint для получения метрик
    @app.get("/metrics")
    async def get_metrics():
        return Response(
            content=generate_latest(registry),
            media_type=CONTENT_TYPE_LATEST
        )