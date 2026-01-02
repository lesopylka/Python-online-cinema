import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import psycopg

DATABASE_URL = os.getenv("DATABASE_URL")

app = FastAPI(title="Cinema CMS")

class OverrideIn(BaseModel):
    movie_id: int
    language: str = "ru"
    description: str
    editor_id: str | None = None

@app.get("/health")
def health():
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

