"""Read-only access to backend/data/wind.sqlite.

The database is opened with mode=ro and immutable=1: it can never be written, and it works
on read-only filesystems (such as a serverless deployment). Queries use no user input.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.core.selection import ForecastBook, ForecastRow

UTC = timezone.utc


def parse_utc(s: str) -> datetime:
    """Parse the stored form 2026-01-15T10:30:00Z into an aware UTC datetime."""
    return datetime.fromisoformat(s[:-1]).replace(tzinfo=UTC)


@dataclass(frozen=True)
class Dataset:
    book: ForecastBook
    actuals: dict[datetime, float]   # half-hourly actuals keyed by start time
    meta: dict[str, str]


class WindRepository:
    def __init__(self, db_path: str | Path) -> None:
        path = Path(db_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"database not found: {path}")
        self._uri = f"{path.as_uri()}?mode=ro&immutable=1"

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._uri, uri=True)

    def meta(self) -> dict[str, str]:
        con = self._connect()
        try:
            return dict(con.execute("SELECT key, value FROM meta"))
        finally:
            con.close()

    def forecast_rows(self) -> list[ForecastRow]:
        con = self._connect()
        try:
            cur = con.execute("SELECT publish_time, start_time, wind_mw FROM forecasts")
            return [ForecastRow(parse_utc(p), parse_utc(s), float(mw)) for p, s, mw in cur]
        finally:
            con.close()

    def actuals(self) -> dict[datetime, float]:
        con = self._connect()
        try:
            cur = con.execute("SELECT start_time, wind_mw FROM actuals_half_hourly")
            return {parse_utc(s): float(mw) for s, mw in cur}
        finally:
            con.close()

    def load(self) -> Dataset:
        return Dataset(book=ForecastBook(self.forecast_rows()), actuals=self.actuals(), meta=self.meta())