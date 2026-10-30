"""Application settings, read from environment variables with safe defaults."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# backend/app/config.py -> backend/data/wind.sqlite (shipped inside backend/ so the API can find it)
DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "wind.sqlite"


@dataclass(frozen=True)
class Settings:
    db_path: Path


def get_settings() -> Settings:
    override = os.environ.get("WIND_DB_PATH")
    return Settings(db_path=Path(override) if override else DEFAULT_DB_PATH)