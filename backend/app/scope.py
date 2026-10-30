"""Project scope: which dates the app covers (see DATA_NOTES.md section 8).

Purchase decisions are made on 1-31 January 2026, so the delivery days are 2 January
to 1 February 2026.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Iterator

FIRST_DECISION = date(2026, 1, 1)
LAST_DECISION = date(2026, 1, 31)
FIRST_DELIVERY = date(2026, 1, 2)
LAST_DELIVERY = date(2026, 2, 1)


def delivery_days(first: date = FIRST_DELIVERY, last: date = LAST_DELIVERY) -> Iterator[date]:
    d = first
    while d <= last:
        yield d
        d += timedelta(days=1)


def is_valid_delivery_date(d: date) -> bool:
    return FIRST_DELIVERY <= d <= LAST_DELIVERY