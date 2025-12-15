# app/main.py
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import time
import structlog
from typing import Dict, Any
from contextlib import asynccontextmanager

from app.config import get_settings
from app.database import engine, Base
from app.monitoring.metrics import setup_metrics, instrument_app
from app.monitoring.logging import setup_logging
from app.activity.endpoints import router as activity_router
from app.streaming.endpoints import router as streaming_router

settings = get_settings()
logger = structlog.get_logger()

# Настройка логирования
setup_logging(settings.LOG_LEVEL)


# Lifespan менеджер для startup/shutdown событий
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code
    logger.info("Starting application", version=settings.APP_VERSION)

    # Создание таблиц
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error("Failed to create database tables", error=str(e))

    # Проверка подключений
    await check_dependencies()

    yield  # Здесь приложение работает

    # Shutdown code
    logger.info("Shutting down application")


async def check_dependencies():
    """Проверка подключения к зависимостям"""
    from app.database import check_db_connection

    try:
        await check_db_connection()
        logger.info("Database connection: OK")
    except Exception as e:
        logger.error("Database connection: FAILED", error=str(e))

    # Временно закомментируйте Redis и Storage проверки
    # try:
    #     from app.activity.storage import check_redis_connection
    #     await check_redis_connection()
    #     logger.info("Redis connection: OK")
    # except Exception as e:
    #     logger.error("Redis connection: FAILED", error=str(e))

    # try:
    #     from app.streaming.storage import check_storage_connection
    #     await check_storage_connection()
    #     logger.info("Storage connection: OK")
    # except Exception as e:
    #     logger.error("Storage connection: FAILED", error=str(e))

    logger.info("Redis check: SKIPPED (not configured)")
    logger.info("Storage check: SKIPPED (not configured)")


# Создание FastAPI приложения с lifespan
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan  # Подключаем lifespan менеджер
)

# Настройка метрик
setup_metrics()
instrument_app(app)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)


# Логирование запросов
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()

    # Пропускаем метрики и health checks
    if request.url.path in ["/metrics", "/health"]:
        return await call_next(request)

    # Логируем входящий запрос
    logger.info(
        "request_started",
        method=request.method,
        path=request.url.path,
        client_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    try:
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000

        # Логируем ответ
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            process_time_ms=process_time,
        )

        # Добавляем время обработки в заголовки
        response.headers["X-Process-Time"] = f"{process_time:.2f}ms"

        return response

    except Exception as exc:
        process_time = (time.time() - start_time) * 1000
        logger.error(
            "request_failed",
            method=request.method,
            path=request.url.path,
            error=str(exc),
            process_time_ms=process_time,
            exc_info=True,
        )
        raise


# Обработчики ошибок
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        error=str(exc),
        exc_info=True,
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.DEBUG else "Contact support",
            "request_id": request.state.request_id if hasattr(request.state, "request_id") else None,
        },
    )


# Health check
@app.get("/health")
async def health_check() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": time.time(),
    }


# Подключение роутеров
app.include_router(
    activity_router,
    prefix="/api/v1/activity",
    tags=["Activity"],
)

app.include_router(
    streaming_router,
    prefix="/api/v1/stream",
    tags=["Streaming"],
)