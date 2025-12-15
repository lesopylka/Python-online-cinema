# app/config.py
from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache
import os


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Online Cinema Backend"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4

    # CORS
    CORS_ORIGINS: list = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Database
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "cinema"
    POSTGRES_USER: str = "cinema_user"
    POSTGRES_PASSWORD: str = "cinema_pass"
    DATABASE_URL: str = "sqlite+aiosqlite:///./cinema.db"
    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_URL: str = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

    # ClickHouse
    CLICKHOUSE_HOST: str = "localhost"
    CLICKHOUSE_PORT: int = 9000
    CLICKHOUSE_DB: str = "cinema_analytics"
    CLICKHOUSE_USER: str = "default"
    CLICKHOUSE_PASSWORD: str = ""

    # Storage (S3/MinIO)
    STORAGE_ENDPOINT: str = "http://localhost:9000"
    STORAGE_ACCESS_KEY: str = "minioadmin"
    STORAGE_SECRET_KEY: str = "minioadmin"
    STORAGE_BUCKET_RAW: str = "cinema-raw"
    STORAGE_BUCKET_PROCESSED: str = "cinema-processed"
    STORAGE_REGION: str = "us-east-1"
    STORAGE_SECURE: bool = False

    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 1000
    RATE_LIMIT_PER_HOUR: int = 10000

    # Activity collection
    ACTIVITY_BATCH_SIZE: int = 100
    ACTIVITY_FLUSH_INTERVAL: int = 10  # seconds
    ACTIVITY_RETENTION_DAYS: int = 90

    # Streaming
    STREAM_CHUNK_SIZE: int = 1024 * 1024  # 1MB
    STREAM_PRESIGNED_URL_EXPIRE: int = 3600  # 1 hour
    HLS_SEGMENT_DURATION: int = 6  # seconds

    # Monitoring
    METRICS_PORT: int = 9090
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()