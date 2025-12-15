# app/activity/storage.py
import redis.asyncio as redis
from redis.exceptions import RedisError
from app.config import get_settings
import structlog

settings = get_settings()
logger = structlog.get_logger()


async def get_redis_client() -> redis.Redis:
    """Создание клиента Redis"""
    try:
        client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True
        )

        # Проверяем подключение
        await client.ping()
        logger.info("Redis client created successfully")
        return client

    except RedisError as e:
        logger.error(f"Failed to create Redis client: {e}")
        raise


async def check_redis_connection() -> bool:
    """Проверка подключения к Redis"""
    try:
        client = await get_redis_client()
        await client.ping()
        logger.info("Redis connection: OK")
        await client.close()
        return True

    except Exception as e:
        logger.warning(f"Redis connection: FAILED - {e}")
        return False


async def store_session_data(session_id: str, data: dict, ttl: int = 3600):
    """Хранение данных сессии в Redis"""
    try:
        client = await get_redis_client()
        await client.hset(f"session:{session_id}", mapping=data)
        await client.expire(f"session:{session_id}", ttl)

    except Exception as e:
        logger.error(f"Failed to store session data: {e}")


async def get_session_data(session_id: str) -> dict:
    """Получение данных сессии из Redis"""
    try:
        client = await get_redis_client()
        data = await client.hgetall(f"session:{session_id}")
        return data

    except Exception as e:
        logger.error(f"Failed to get session data: {e}")
        return {}


async def increment_counter(key: str, amount: int = 1, ttl: int = None) -> int:
    """Инкремент счетчика в Redis"""
    try:
        client = await get_redis_client()
        result = await client.incrby(key, amount)

        if ttl:
            await client.expire(key, ttl)

        return result

    except Exception as e:
        logger.error(f"Failed to increment counter: {e}")
        return 0