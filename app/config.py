from __future__ import annotations
from pathlib import Path
import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict


def load_config(path: str = "config.yaml") -> dict:
    """
    Загружает конфигурацию приложения из YAML-файла.
    """

    cfg = Path(path)

    if not cfg.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    with cfg.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class Settings(BaseSettings):
    kafka_bootstrap_servers: str | None = "localhost:9092"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
