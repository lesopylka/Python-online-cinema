# app/database.py
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import get_settings
import os

settings = get_settings()

# Определяем URL для SQLite
if "sqlite" in settings.DATABASE_URL:
    # Для SQLite убираем замену на asyncpg
    database_url = settings.DATABASE_URL
else:
    # Для PostgreSQL оставляем замену
    database_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

# Асинхронный engine
engine = create_async_engine(
    database_url,
    echo=settings.DEBUG,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
    pool_recycle=3600,
    # Дополнительные параметры для SQLite
    connect_args={"check_same_thread": False} if "sqlite" in database_url else {}
)

# Фабрика сессий
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Базовый класс для моделей
Base = declarative_base()

async def get_db_session() -> AsyncSession:
    """Dependency для получения сессии БД"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def check_db_connection():
    """Проверка подключения к БД"""
    async with engine.begin() as conn:
        await conn.execute("SELECT 1")