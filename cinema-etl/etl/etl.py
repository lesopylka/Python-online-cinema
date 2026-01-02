import os
import json
import re
import requests
import psycopg

# === ENV ===
DB = os.getenv("DATABASE_URL")
CMS = os.getenv("CMS_URL")

# === UTILS ===
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

# === LOAD PARTNER DATA ===
with open("partner_movies.json", encoding="utf-8") as f:
    partner = json.load(f)

# === MERGE LOGIC ===
final = []

for p in partner:
    movie_id = p["movie_id"]
    title = p["title"]
    language = p.get("language", "ru")

    cms = cms_override(movie_id, language)

    if cms:
        description = clean(cms["description"])
        source_used = "cms"
    else:
        description = clean(p.get("description"))
        source_used = "partner"

    final.append(
        (movie_id, title, language, description, source_used)
    )

# === UPSERT TO POSTGRES ===
with psycopg.connect(DB) as conn:
    for row in final:
        conn.execute(
            """
            INSERT INTO movies (movie_id, title, language, description, source_used)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (movie_id)
            DO UPDATE SET
                description = EXCLUDED.description,
                source_used = EXCLUDED.source_used,
                updated_at = NOW()
            """,
            row,
        )
    conn.commit()

print("ETL DONE")


