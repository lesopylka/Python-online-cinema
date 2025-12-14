from __future__ import annotations

import yaml
from pathlib import Path


def load_config(path: str = "config.yaml") -> dict:
    """
    Загружает конфигурацию приложения из YAML-файла.
    """

    cfg = Path(path)

    if not cfg.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    with cfg.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)
