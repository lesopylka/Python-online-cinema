import os
import json
import re
import requests
import psycopg


DB = os.getenv("DATABASE_URL")
CMS = os.getenv("CMS_URL")


def clean(text: str | None) -> str | None:
    if not text:
        return None
    return " ".join(re.sub(r"<.*?>", "", text).split())[:4000]


def cms_override(movie_id: int, lang: str):
    try:
        r = requests.get(
            f"{CMS}/overrides/{movie_id}",
            params={"lang": lang},
            timeout=5,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def normalize_actor_obj(a: dict) -> tuple[int, str, str | None, str | None]:
    actor_id = int(a["actor_id"])
    full_name = clean(a.get("full_name")) or ""
    birth_date = a.get("birth_date")
    role_name = clean(a.get("role_name"))
    if not full_name:
        raise ValueError(f"actor full_name is empty for actor_id={actor_id}")
    return actor_id, full_name, birth_date, role_name


if not DB:
    raise RuntimeError("DATABASE_URL is not set")
if not CMS:
    raise RuntimeError("CMS_URL is not set")

with open("partner_movies.json", encoding="utf-8") as f:
    partner = json.load(f)

movies_rows: list[tuple[int, str, str, str | None, str]] = []
actors_rows: dict[int, tuple[int, str, str | None]] = {}
links_rows: list[tuple[int, int, str | None]] = []

for p in partner:
    movie_id = int(p["movie_id"])
    title = clean(p.get("title")) or ""
    language = p.get("language", "ru")

    if not title:
        raise ValueError(f"movie title is empty for movie_id={movie_id}")

    partner_desc = clean(p.get("description"))
    partner_actors_raw = p.get("actors", []) or []

    cms = cms_override(movie_id, language)

    if cms:
        description = clean(cms.get("description")) or partner_desc
        source_used = "cms"
        actors_raw = cms.get("actors", None)
        if actors_raw is None:
            actors_raw = partner_actors_raw
    else:
        description = partner_desc
        source_used = "partner"
        actors_raw = partner_actors_raw

    movies_rows.append((movie_id, title, language, description, source_used))

    for a in (actors_raw or []):
        actor_id, full_name, birth_date, role_name = normalize_actor_obj(a)
        actors_rows[actor_id] = (actor_id, full_name, birth_date)
        links_rows.append((movie_id, actor_id, role_name))

with psycopg.connect(DB) as conn:
    for row in movies_rows:
        conn.execute(
            """
            INSERT INTO movies (movie_id, title, language, description, source_used)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (movie_id)
            DO UPDATE SET
                title = EXCLUDED.title,
                language = EXCLUDED.language,
                description = EXCLUDED.description,
                source_used = EXCLUDED.source_used,
                updated_at = NOW()
            """,
            row,
        )

    for actor_id, full_name, birth_date in actors_rows.values():
        conn.execute(
            """
            INSERT INTO actors (actor_id, full_name, birth_date)
            VALUES (%s, %s, %s)
            ON CONFLICT (actor_id)
            DO UPDATE SET
                full_name = EXCLUDED.full_name,
                birth_date = EXCLUDED.birth_date,
                updated_at = NOW()
            """,
            (actor_id, full_name, birth_date),
        )

    for movie_id, actor_id, role_name in links_rows:
        conn.execute(
            """
            INSERT INTO movie_actors (movie_id, actor_id, role_name)
            VALUES (%s, %s, %s)
            ON CONFLICT (movie_id, actor_id)
            DO UPDATE SET
                role_name = EXCLUDED.role_name,
                updated_at = NOW()
            """,
            (movie_id, actor_id, role_name),
        )

    conn.commit()

print("ETL DONE")
