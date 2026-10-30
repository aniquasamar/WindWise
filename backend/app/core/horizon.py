"""Error against forecast horizon (horizon = target time minus publish time, in hours).

Two separate views, never mixed:

* decision-time view: only the forecast the buyer actually used (a single run per day), so the
  horizon spans roughly 16 to 40 hours;
* full curve: every published run for every target hour, from days ahead down to targets that
  have already elapsed. This is context ("do forecasts improve as delivery approaches?") and
  not what the buyer saw. Samples overlap heavily, so treat it as descriptive.

Targets whose horizon is zero or negative are "already elapsed": the run was published after
the hour had begun. They are not forecasts, and sit in their own bucket.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, Mapping, Sequence

from .alignment import hourly_actual
from .pipeline import DayEvaluation
from .selection import ForecastBook
from .stats import Metrics, summarize
from .timeutils import day_bounds_utc, hourly_grid

ELAPSED = -1


def bucket_index(horizon_h: float, width: float) -> int:
    """-1 for horizons <= 0 (elapsed); otherwise k such that horizon is in (k*width, (k+1)*width]."""
    if horizon_h <= 0:
        return ELAPSED
    return int(math.ceil(horizon_h / width)) - 1


def bucket_label(index: int, width: float) -> str:
    if index == ELAPSED:
        return "already elapsed (0 h or less)"
    return f"{index * width:g} to {(index + 1) * width:g} h"


@dataclass(frozen=True)
class HorizonBucket:
    index: int
    label: str
    lower_h: float      # exclusive lower edge (None-like for elapsed: use -inf)
    upper_h: float      # inclusive upper edge
    metrics: Metrics

    @property
    def elapsed(self) -> bool:
        return self.index == ELAPSED


def _to_buckets(groups: Mapping[int, tuple[list[float], list[float]]], width: float) -> list[HorizonBucket]:
    out = []
    for idx in sorted(groups):
        f, a = groups[idx]
        lo = float("-inf") if idx == ELAPSED else idx * width
        hi = 0.0 if idx == ELAPSED else (idx + 1) * width
        out.append(HorizonBucket(idx, bucket_label(idx, width), lo, hi, summarize(f, a)))
    return out


def decision_time_horizon(evaluations: Iterable[DayEvaluation], width: float = 6.0) -> list[HorizonBucket]:
    """Accuracy of the forecast the buyer used, grouped by its horizon."""
    groups: dict[int, tuple[list[float], list[float]]] = defaultdict(lambda: ([], []))
    for ev in evaluations:
        for p in ev.scored():
            f, a = groups[bucket_index(p.horizon_h, width)]
            f.append(p.forecast_mw)
            a.append(p.actual_mw)  # type: ignore[arg-type]
    return _to_buckets(groups, width)


def full_horizon_curve(
    book: ForecastBook,
    actuals: Mapping[datetime, float],
    delivery_dates: Sequence[date],
    width: float = 12.0,
) -> list[HorizonBucket]:
    """Accuracy of every published forecast for every scored target hour, by horizon."""
    groups: dict[int, tuple[list[float], list[float]]] = defaultdict(lambda: ([], []))
    for d in delivery_dates:
        start, end = day_bounds_utc(d)
        for target in hourly_grid(start, end):
            actual = hourly_actual(actuals, target)
            if actual is None:
                continue
            for publish, mw in book.publications_for(target):
                h = (target - publish).total_seconds() / 3600.0
                f, a = groups[bucket_index(h, width)]
                f.append(mw)
                a.append(actual)
    return _to_buckets(groups, width)