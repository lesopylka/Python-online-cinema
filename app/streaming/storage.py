# app/streaming/storage.py
from minio import Minio
from minio.error import S3Error
from app.config import get_settings
import structlog

settings = get_settings()
logger = structlog.get_logger()


def get_storage_client() -> Minio:
    """Создание клиента MinIO/S3"""
    try:
        # Убираем протокол из endpoint
        endpoint = settings.STORAGE_ENDPOINT
        if endpoint.startswith("http://"):
            endpoint = endpoint[7:]
        elif endpoint.startswith("https://"):
            endpoint = endpoint[8:]

        client = Minio(
            endpoint=endpoint,
            access_key=settings.STORAGE_ACCESS_KEY,
            secret_key=settings.STORAGE_SECRET_KEY,
            secure=settings.STORAGE_SECURE
        )

        logger.info("Storage client created successfully")
        return client

    except Exception as e:
        logger.error(f"Failed to create storage client: {e}")
        raise


def check_storage_connection() -> bool:
    """Проверка подключения к хранилищу"""
    try:
        client = get_storage_client()

        # Проверяем существование бакетов, создаем если нет
        buckets = [settings.STORAGE_BUCKET_RAW, settings.STORAGE_BUCKET_PROCESSED]

        for bucket in buckets:
            if not client.bucket_exists(bucket):
                client.make_bucket(bucket)
                logger.info(f"Created bucket: {bucket}")

        logger.info("Storage connection: OK")
        return True

    except S3Error as e:
        logger.warning(f"Storage connection failed: {e}")
        return False
    except Exception as e:
        logger.warning(f"Storage connection failed: {e}")
        return False


def get_presigned_url(bucket: str, object_name: str, expires: int = 3600) -> str:
    """Получение предварительно подписанного URL"""
    try:
        client = get_storage_client()
        url = client.presigned_get_object(
            bucket_name=bucket,
            object_name=object_name,
            expires=expires
        )
        return url

    except Exception as e:
        logger.error(f"Failed to generate presigned URL: {e}")
        return None