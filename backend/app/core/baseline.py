"""Persistence baseline: the actual for the same hour 48 hours earlier.

Why 48 hours and not "yesterday": at the cutoff on the decision date, the previous
calendar day (delivery day minus 1 is the decision date itself) is not finished, so its
actuals do not exist yet. The latest complete day is two days before delivery.

This module also checks availability explicitly. An actual only counts as known at the
cutoff if its hour ended, plus the publication lag, at or before the cutoff.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Mapping, Optional

from .alignment import hourly_actual
from .timeutils import HOUR

# Actuals normally appear about 30 minutes after a period ends; the slowest seen was
# 2.42 hours (DATA_NOTES.md section 3). Use a conservative margin.
ACTUAL_PUBLICATION_LAG = timedelta(hours=2.5)
BASELINE_LAG = timedelta(hours=48)


def actual_known_at(hour_start: datetime, cutoff: datetime) -> bool:
    """True if the hourly actual starting at `hour_start` would have been published by `cutoff`."""
    return hour_start + HOUR + ACTUAL_PUBLICATION_LAG <= cutoff


def persistence_baseline(
    actuals: Mapping[datetime, float], target: datetime, cutoff: datetime
) -> Optional[float]:
    """Baseline for `target`, using only actuals known at `cutoff`. None if unavailable."""
    source = target - BASELINE_LAG
    if not actual_known_at(source, cutoff):
        return None
    return hourly_actual(actuals, source)