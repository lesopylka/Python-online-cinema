# .env
DEBUG=True
ENVIRONMENT=development

# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=cinema
POSTGRES_USER=cinema_user
POSTGRES_PASSWORD=cinema_pass

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# ClickHouse (опционально)
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=9000
CLICKHOUSE_DB=cinema_analytics
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=

# Storage (MinIO/S3)
STORAGE_ENDPOINT=http://localhost:9000
STORAGE_ACCESS_KEY=minioadmin
STORAGE_SECRET_KEY=minioadmin
STORAGE_BUCKET_RAW=cinema-raw
STORAGE_BUCKET_PROCESSED=cinema-processed

# Security
SECRET_KEY=your-secret-key-change-this-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=30

LOG_LEVEL=INFO