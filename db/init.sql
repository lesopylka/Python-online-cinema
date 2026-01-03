CREATE TABLE IF NOT EXISTS movie_description_overrides (
  movie_id    BIGINT NOT NULL,
  language    TEXT   NOT NULL,
  description TEXT   NOT NULL,
  editor_id   TEXT,
  updated_at  TIMESTAMP NOT NULL DEFAULT NOW(),
  PRIMARY KEY (movie_id, language)
);

CREATE TABLE IF NOT EXISTS movies (
  movie_id      BIGINT PRIMARY KEY,
  title         TEXT NOT NULL,
  language      TEXT NOT NULL DEFAULT 'ru',
  description   TEXT,
  source_used   TEXT NOT NULL,
  updated_at    TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_movies_title ON movies (title);
ALTER TABLE movies
ADD COLUMN IF NOT EXISTS video_key TEXT;
CREATE INDEX IF NOT EXISTS idx_movies_video_key ON movies (video_key);
