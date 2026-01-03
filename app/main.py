import logging
import os
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from confluent_kafka import Producer
import psycopg
from app.config import settings, load_config
from app.observability import attach_observability


config = load_config("config.yaml")  # загружаем конфигурация из yaml

log = logging.getLogger("app")  # создается логгер приложения

app = FastAPI(title=config["app"]["name"])  # создаётся FastAPI-приложение

attach_observability(app, config)  # подключаются логи и метрики


DATABASE_URL = os.getenv("DATABASE_URL")

producer: Producer | None = None


class OverrideIn(BaseModel):
    movie_id: int
    language: str = "ru"
    description: str
    editor_id: str | None = None


@app.on_event("startup")
async def startup_event():
    """
    При старте приложения пытаемся подключиться к Kafka.
    Если Kafka недоступна — приложение всё равно стартует.
    """
    global producer

    if not settings.kafka_bootstrap_servers:
        log.warning("Kafka disabled: kafka_bootstrap_servers is empty")
        producer = None
        return

    try:
        producer = Producer({
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "socket.timeout.ms": 2000,
            "message.timeout.ms": 3000,
            "log_level": 3,
        })
        log.info("Kafka producer initialized")
    except Exception as e:
        producer = None
        log.warning(f"Kafka is not available, continuing without it: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """
    Корректно останавливаем Kafka producer при завершении приложения.
    """
    global producer
    if producer is None:
        return
    try:
        producer.flush(2.0)
    except Exception:
        pass
    producer = None


@app.get("/ping")
def ping():
    log.info("ping called")
    return {"pong": True}


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/kafka-test")
def kafka_test():
    if producer is None:
        return {"ok": False, "error": "producer is None"}

    producer.produce("test-topic", value=b"hello")
    producer.flush(2.0)
    return {"ok": True}


@app.post("/overrides")
def upsert_override(payload: OverrideIn):
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute(
            """
            INSERT INTO movie_description_overrides
            (movie_id, language, description, editor_id)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (movie_id, language)
            DO UPDATE SET
                description = EXCLUDED.description,
                editor_id = EXCLUDED.editor_id,
                updated_at = NOW()
            """,
            (payload.movie_id, payload.language, payload.description, payload.editor_id),
        )
        conn.commit()
    return {"status": "ok"}


@app.get("/overrides/{movie_id}")
def get_override(movie_id: int, lang: str = "ru"):
    with psycopg.connect(DATABASE_URL) as conn:
        row = conn.execute(
            """
            SELECT movie_id, language, description, editor_id, updated_at
            FROM movie_description_overrides
            WHERE movie_id = %s AND language = %s
            """,
            (movie_id, lang),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="override not found")

    return {
        "movie_id": row[0],
        "language": row[1],
        "description": row[2],
        "editor_id": row[3],
        "updated_at": row[4].isoformat(),
    }

#разрешаем фронту ходить в API из браузера (иначе будет CORS ошибка)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  #можно сузить до ["http://localhost:8080"] 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/movies")
def list_movies(
    q: str | None = None,
    lang: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """
    Список фильмов из таблицы movies.
    Поддерживает:
    - q: поиск по подстроке title (ILIKE)
    - lang: фильтр по language
    - limit/offset: пагинация
    """
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL is not set")

    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    where = []
    params: list = []

    if q:
        where.append("title ILIKE %s")
        params.append(f"%{q}%")

    if lang:
        where.append("language = %s")
        params.append(lang)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    with psycopg.connect(DATABASE_URL) as conn:
        rows = conn.execute(
            f"""
            SELECT movie_id, title, language, description, source_used, updated_at
            FROM movies
            {where_sql}
            ORDER BY title
            LIMIT %s OFFSET %s
            """,
            (*params, limit, offset),
        ).fetchall()

    return [
        {
            "movie_id": r[0],
            "title": r[1],
            "language": r[2],
            "description": r[3],
            "source_used": r[4],
            "updated_at": r[5].isoformat() if r[5] else None,
        }
        for r in rows
    ]
