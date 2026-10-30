"""Application settings, read from environment variables with safe defaults."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# backend/app/config.py -> backend/data/wind.sqlite (shipped inside backend/ so the API can find it)
DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "wind.sqlite"
DEFAULT_ALLOWED_HOSTS = ("localhost", "127.0.0.1", "testserver", "*.vercel.app")
DEFAULT_RATE_LIMIT_PER_MIN = 120


@dataclass(frozen=True)
class Settings:
    db_path: Path
    allowed_hosts: tuple[str, ...] = DEFAULT_ALLOWED_HOSTS
    allowed_origins: tuple[str, ...] = ()           # empty: no cross-origin access (same-origin deployment)
    rate_limit_per_min: int = DEFAULT_RATE_LIMIT_PER_MIN   # 0 turns the limiter off
    trust_proxy: bool = False                        # read client IP from X-Forwarded-For (only behind a trusted proxy)


def _csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return tuple(x.strip() for x in raw.split(",") if x.strip())


def get_settings() -> Settings:
    override = os.environ.get("WIND_DB_PATH")
    on_vercel = bool(os.environ.get("VERCEL"))
    trust_default = "1" if on_vercel else "0"
    return Settings(
        db_path=Path(override) if override else DEFAULT_DB_PATH,
        allowed_hosts=_csv("ALLOWED_HOSTS", DEFAULT_ALLOWED_HOSTS),
        allowed_origins=_csv("ALLOWED_ORIGINS", ()),
        rate_limit_per_min=int(os.environ.get("RATE_LIMIT_PER_MIN", DEFAULT_RATE_LIMIT_PER_MIN)),
        trust_proxy=os.environ.get("TRUST_PROXY", trust_default) == "1",
    )