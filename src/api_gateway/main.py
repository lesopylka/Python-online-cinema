from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging
from .middleware import AuthMiddleware, LoggingMiddleware, RateLimitMiddleware
from .routes import router as api_router
from src.config.settings import settings
from src.monitoring.metrics import setup_metrics
from src.shared.logging import setup_logging

# Настройка логирования
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Online Cinema API Gateway",
    description="Единая точка входа для микросервисной архитектуры онлайн-кинотеатра",
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

# Кастомные middleware (порядок важен!)
app.add_middleware(LoggingMiddleware)
app.add_middleware(RateLimitMiddleware, limit=100, window=60)
app.add_middleware(AuthMiddleware)

# Подключаем роуты
app.include_router(api_router)

# Настройка метрик
setup_metrics(app)

@app.get("/")
async def root():
    """Корневой endpoint с информацией о системе."""
    return {
        "message": "Online Cinema API Gateway",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "openapi": "/openapi.json",
            "metrics": "/metrics"
        }
    }

@app.get("/health")
async def health_check():
    """Health check для балансировщиков нагрузки и мониторинга."""
    return {
        "status": "healthy",
        "service": "api-gateway",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": settings.ENVIRONMENT
    }

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Глобальный обработчик HTTP исключений."""
    logger.warning(f"HTTP error {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Обработчик ошибок валидации."""
    logger.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "status_code": 422,
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Глобальный обработчик непредвиденных исключений."""
    logger.exception(f"Unexpected error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "status_code": 500,
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@app.on_event("startup")
async def startup_event():
    """Действия при запуске приложения."""
    logger.info("Starting API Gateway...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"CORS origins: {settings.CORS_ORIGINS}")

@app.on_event("shutdown")
async def shutdown_event():
    """Действия при остановке приложения."""
    logger.info("Shutting down API Gateway...")