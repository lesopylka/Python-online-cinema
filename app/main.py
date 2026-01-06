import logging
import os
import re
import psycopg
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from minio import Minio
from pydantic import BaseModel
from app.config import load_config
from app.observability import attach_observability

config = load_config("config.yaml")
log = logging.getLogger("app")

app = FastAPI(title=config["app"]["name"])
attach_observability(app, config)

DATABASE_URL = os.getenv("DATABASE_URL")

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://minio:9000")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "minio")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "minio12345")
S3_BUCKET = os.getenv("S3_BUCKET", "cinema")


class OverrideIn(BaseModel):
    movie_id: int
    language: str = "ru"
    description: str
    editor_id: str | None = None


def db_conn():
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL is not set")
    return psycopg.connect(DATABASE_URL)


def s3_client() -> Minio:
    if not S3_ENDPOINT:
        raise HTTPException(status_code=500, detail="S3_ENDPOINT is not set")
    endpoint = S3_ENDPOINT.replace("http://", "").replace("https://", "")
    secure = S3_ENDPOINT.startswith("https://")
    return Minio(endpoint, access_key=S3_ACCESS_KEY, secret_key=S3_SECRET_KEY, secure=secure)


@app.get("/ping")
def ping():
    log.info("ping called")
    return {"pong": True}


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/overrides")
def upsert_override(payload: OverrideIn):
    with db_conn() as conn:
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
    with db_conn() as conn:
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

    with db_conn() as conn:
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
    with db_conn() as conn:
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


@app.get("/movies/{movie_id}/actors")
def movie_actors(movie_id: int):
    with db_conn() as conn:
        rows = conn.execute(
            """
            SELECT a.actor_id, a.full_name, a.birth_date, ma.role_name
            FROM movie_actors ma
            JOIN actors a ON a.actor_id = ma.actor_id
            WHERE ma.movie_id = %s
            ORDER BY a.full_name
            """,
            (movie_id,),
        ).fetchall()

    return {
        "items": [
            {
                "actor_id": r[0],
                "full_name": r[1],
                "birth_date": r[2].isoformat() if r[2] else None,
                "role_name": r[3],
            }
            for r in rows
        ]
    }


@app.get("/actors")
def list_actors(q: str | None = None, limit: int = 50, offset: int = 0):
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))

    where = []
    params: list = []

    if q:
        where.append("full_name ILIKE %s")
        params.append(f"%{q}%")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    with db_conn() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM actors {where_sql}",
            params,
        ).fetchone()[0]

        rows = conn.execute(
            f"""
            SELECT actor_id, full_name, birth_date, updated_at
            FROM actors
            {where_sql}
            ORDER BY full_name
            LIMIT %s OFFSET %s
            """,
            (*params, limit, offset),
        ).fetchall()

    return {
        "items": [
            {
                "actor_id": r[0],
                "full_name": r[1],
                "birth_date": r[2].isoformat() if r[2] else None,
                "updated_at": r[3].isoformat() if r[3] else None,
            }
            for r in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@app.get("/actors/{actor_id}")
def get_actor(actor_id: int):
    with db_conn() as conn:
        row = conn.execute(
            """
            SELECT actor_id, full_name, birth_date, updated_at
            FROM actors
            WHERE actor_id = %s
            """,
            (actor_id,),
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="actor not found")

        movies = conn.execute(
            """
            SELECT m.movie_id, m.title, ma.role_name
            FROM movie_actors ma
            JOIN movies m ON m.movie_id = ma.movie_id
            WHERE ma.actor_id = %s
            ORDER BY m.title
            """,
            (actor_id,),
        ).fetchall()

    return {
        "actor_id": row[0],
        "full_name": row[1],
        "birth_date": row[2].isoformat() if row[2] else None,
        "updated_at": row[3].isoformat() if row[3] else None,
        "movies": [{"movie_id": r[0], "title": r[1], "role_name": r[2]} for r in movies],
    }


@app.get("/stream/{name}")
def stream_video(name: str, request: Request):
    c = s3_client()

    try:
        stat = c.stat_object(S3_BUCKET, name)
    except Exception:
        raise HTTPException(status_code=404, detail="video not found")

    size = stat.size
    range_header = request.headers.get("range")

    def iter_data(resp, chunk=1024 * 1024):
        try:
            for part in resp.stream(chunk):
                yield part
        finally:
            try:
                resp.close()
            except Exception:
                pass

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Type": "video/mp4",
    }

    if not range_header:
        resp = c.get_object(S3_BUCKET, name)
        headers["Content-Length"] = str(size)
        return StreamingResponse(iter_data(resp), status_code=200, headers=headers)

    m = re.match(r"bytes=(\d+)-(\d*)", range_header)
    if not m:
        resp = c.get_object(S3_BUCKET, name)
        headers["Content-Length"] = str(size)
        return StreamingResponse(iter_data(resp), status_code=200, headers=headers)

    start = int(m.group(1))
    end = int(m.group(2)) if m.group(2) else size - 1

    if start >= size:
        raise HTTPException(status_code=416, detail="range not satisfiable")

    end = min(end, size - 1)
    length = end - start + 1

    resp = c.get_object(S3_BUCKET, name, offset=start, length=length)

    headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    headers["Content-Length"] = str(length)

    return StreamingResponse(iter_data(resp), status_code=206, headers=headers)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
