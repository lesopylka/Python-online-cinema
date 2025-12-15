from pydantic_settings import BaseSettings
from typing import List, Optional
from pydantic import validator
import json


class Settings(BaseSettings):
    # Общие настройки
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    
    # API Gateway
    API_GATEWAY_HOST: str = "0.0.0.0"
    API_GATEWAY_PORT: int = 8000
    
    # Сервисы
    USER_SERVICE_URL: str = "http://user-service:8001"
    CATALOG_SERVICE_URL: str = "http://catalog-service:8002"
    SEARCH_SERVICE_URL: str = "http://search-service:8003"
    STREAMING_SERVICE_URL: str = "http://streaming-service:8004"
    ANALYTICS_SERVICE_URL: str = "http://analytics-service:8005"
    NOTIFICATION_SERVICE_URL: str = "http://notification-service:8006"
    
    # PostgreSQL
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "cinema_user"
    POSTGRES_PASSWORD: str = "cinema_password"
    POSTGRES_DB: str = "cinema"
    
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    
    # Elasticsearch
    ELASTICSEARCH_HOST: str = "elasticsearch"
    ELASTICSEARCH_PORT: int = 9200
    
    @property
    def ELASTICSEARCH_URL(self) -> str:
        return f"http://{self.ELASTICSEARCH_HOST}:{self.ELASTICSEARCH_PORT}"
    
    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_TOPIC_USER_ACTIVITY: str = "user_activity"
    KAFKA_TOPIC_MOVIE_INDEX: str = "movie_index"
    KAFKA_TOPIC_NOTIFICATIONS: str = "notifications"
    
    # JWT
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    
    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v
    
    # Хранилище
    S3_ENDPOINT: str = "minio:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET_MEDIA: str = "media"
    S3_BUCKET_THUMBNAILS: str = "thumbnails"
    S3_SECURE: bool = False
    
    # Мониторинг
    PROMETHEUS_PORT: int = 9090
    GRAFANA_PORT: int = 3000
    JAEGER_HOST: str = "jaeger"
    JAEGER_PORT: int = 6831
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()