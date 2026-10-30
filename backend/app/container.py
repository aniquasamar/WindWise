"""Builds the analytics service once per process (warm serverless instances reuse it)."""
from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.repository.sqlite_repo import WindRepository
from app.services import AnalyticsService


@lru_cache(maxsize=1)
def get_service() -> AnalyticsService:
    return AnalyticsService(WindRepository(get_settings().db_path).load())