"""Time handling. Everything internal is timezone-aware UTC; the UK clock is used only
to turn a local cutoff (for example 09:00) and a local delivery day into UTC instants.

January is outside British Summer Time, so UK time equals UTC for the whole project
scope. The conversion is still done properly with the real UK timezone, so the logic is
also correct for other months (and a test proves it).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc
LONDON = ZoneInfo("Europe/London")
HOUR = timedelta(hours=1)
HALF_HOUR = timedelta(minutes=30)


def decision_date_for(delivery_date: date) -> date:
    """The day the buying decision is made: the day before delivery."""
    return delivery_date - timedelta(days=1)


def cutoff_utc(decision_date: date, cutoff_local: time) -> datetime:
    """UTC instant of a UK-local cutoff time on the decision date.

    Intended for cutoffs well away from the 01:00-02:00 clock-change hour.
    """
    return datetime.combine(decision_date, cutoff_local, tzinfo=LONDON).astimezone(UTC)


def day_bounds_utc(local_date: date) -> tuple[datetime, datetime]:
    """Start (inclusive) and end (exclusive) of a UK calendar day, as UTC instants."""
    start = datetime.combine(local_date, time(0, 0), tzinfo=LONDON).astimezone(UTC)
    end = datetime.combine(local_date + timedelta(days=1), time(0, 0), tzinfo=LONDON).astimezone(UTC)
    return start, end


def hourly_grid(start: datetime, end: datetime) -> list[datetime]:
    """Hourly instants from start (inclusive) to end (exclusive)."""
    out: list[datetime] = []
    t = start
    while t < end:
        out.append(t)
        t += HOUR
    return out