"""Small builders for synthetic test data (all times are UTC)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Callable, Union

from app.core.selection import ForecastBook, ForecastRow
from app.core.timeutils import day_bounds_utc, hourly_grid

UTC = timezone.utc


def dt(y: int, m: int, d: int, h: int = 0, mi: int = 0, s: int = 0) -> datetime:
    return datetime(y, m, d, h, mi, s, tzinfo=UTC)


def day_targets(delivery: date) -> list[datetime]:
    start, end = day_bounds_utc(delivery)
    return hourly_grid(start, end)


def run_for_day(publish: datetime, delivery: date, mw: Union[float, Callable[[int], float]]) -> list[ForecastRow]:
    """One forecast run covering every hour of `delivery`. `mw` is a number or f(hour_index)."""
    rows = []
    for i, t in enumerate(day_targets(delivery)):
        value = mw(i) if callable(mw) else mw
        rows.append(ForecastRow(publish_time=publish, target_time=t, mw=float(value)))
    return rows


def actuals_for_days(first: date, last: date, mw: Union[float, Callable[[datetime], float]]) -> dict[datetime, float]:
    """Half-hourly actuals for every half-hour of first..last inclusive."""
    out: dict[datetime, float] = {}
    t = datetime(first.year, first.month, first.day, tzinfo=UTC)
    end = datetime(last.year, last.month, last.day, tzinfo=UTC) + timedelta(days=1)
    while t < end:
        out[t] = float(mw(t) if callable(mw) else mw)
        t += timedelta(minutes=30)
    return out


def make_window(first: date, n_days: int, fc: Callable[[int, int], float], act: Callable[[int, int], float]):
    """A small synthetic window: one 07:30 run on each decision day and half-hourly actuals.

    fc(day_index, hour) and act(day_index, hour) give MW. Returns (book, actuals, delivery_days).
    """
    rows: list[ForecastRow] = []
    actuals: dict[datetime, float] = {}
    days = [first + timedelta(days=i) for i in range(n_days)]
    for i, d in enumerate(days):
        publish = datetime(d.year, d.month, d.day, tzinfo=UTC) - timedelta(days=1) + timedelta(hours=7, minutes=30)
        rows += run_for_day(publish, d, lambda h, i=i: fc(i, h))
        for h in range(24):
            for half in (0, 30):
                actuals[dt(d.year, d.month, d.day, h, half)] = float(act(i, h))
    return ForecastBook(rows), actuals, days