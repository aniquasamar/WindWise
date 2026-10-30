"""Alignment of half-hourly actuals to hourly forecasts.

An hourly forecast for the hour starting at T is compared with the mean of the two
half-hourly actuals starting at T and T+30 minutes. If either half-hour is missing the
hour has no actual: it is dropped and counted, never filled.
"""
from __future__ import annotations

from datetime import datetime
from typing import Mapping, Optional

from .timeutils import HALF_HOUR


def hourly_actual(actuals: Mapping[datetime, float], hour_start: datetime) -> Optional[float]:
    first = actuals.get(hour_start)
    second = actuals.get(hour_start + HALF_HOUR)
    if first is None or second is None:
        return None
    return (first + second) / 2.0