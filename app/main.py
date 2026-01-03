import logging
import os
from pathlib import Path

import psycopg
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import settings, load_config
from app.observability import attach_observability


config = load_config("config.yaml")
log = logging.getLogger("app")

app = FastAPI(title=config["app"]["name"])
attach_observability(app, config)

DATABASE_URL = os.getenv("DATABASE_URL")

VIDEOS_DIR = Path(os.getenv("VIDEOS_DIR", "./videos")).resolve()


class OverrideIn(BaseModel):
    movie_id: int
    language: str = "ru"
    description: str
    editor_id: str | None = None


@app.get("/ping")
def ping():
    log.info("ping called")
    return {"pong": True}


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/overrides")
def upsert_override(payload: OverrideIn):
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL is not set")

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
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL is not set")

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


@app.get("/movies")
def list_movies(q: str | None = None, lang: str | None = None, limit: int = 50, offset: int = 0):
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL is not set")

    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))

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
        total = conn.execute(
            f"SELECT COUNT(*) FROM movies {where_sql}",
            params,
        ).fetchone()[0]

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

    items = [
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

    return {"items": items, "total": total, "limit": limit, "offset": offset}


@app.get("/movies/{movie_id}")
def get_movie(movie_id: int, lang: str = "ru"):
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL is not set")

    with psycopg.connect(DATABASE_URL) as conn:
        row = conn.execute(
            """
            SELECT movie_id, title, language, description, source_used, updated_at
            FROM movies
            WHERE movie_id = %s
            """,
            (movie_id,),
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="movie not found")

        ovr = conn.execute(
            """
            SELECT description, editor_id, updated_at
            FROM movie_description_overrides
            WHERE movie_id = %s AND language = %s
            """,
            (movie_id, lang),
        ).fetchone()

    movie = {
        "movie_id": row[0],
        "title": row[1],
        "language": row[2],
        "description": row[3],
        "source_used": row[4],
        "updated_at": row[5].isoformat() if row[5] else None,
        "override": None,
        "video": {"url": f"/stream/{row[0]}.mp4"},
    }

    if ovr:
        movie["override"] = {
            "description": ovr[0],
            "editor_id": ovr[1],
            "updated_at": ovr[2].isoformat() if ovr[2] else None,
        }

    return movie


@app.get("/stream/{name}")
def stream_video(name: str):
    p = (VIDEOS_DIR / name).resolve()
    if not str(p).startswith(str(VIDEOS_DIR)):
        raise HTTPException(status_code=400, detail="bad path")

    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="video not found")

    return FileResponse(str(p), media_type="video/mp4")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
