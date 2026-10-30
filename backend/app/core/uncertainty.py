"""Uncertainty of the headline numbers: a day-block bootstrap.

Errors on the same day are strongly related (a missed storm is missed for hours), so 744 hourly
errors behave more like 31 independent days. The bootstrap therefore resamples WHOLE DAYS with
replacement, recomputes the statistic, and reports a percentile interval. The random seed is
fixed, so the same data always gives the same interval.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import date
from typing import Callable, Mapping, Optional, Sequence

from .stats import quantile

DEFAULT_SEED = 20260101
Statistic = Callable[[Sequence[float]], Optional[float]]


@dataclass(frozen=True)
class Interval:
    point: Optional[float]
    low: Optional[float]
    high: Optional[float]
    level: float
    n_days: int
    n_boot: int


def stat_bias(errors: Sequence[float]) -> Optional[float]:
    return sum(errors) / len(errors) if errors else None


def stat_mae(errors: Sequence[float]) -> Optional[float]:
    return sum(abs(e) for e in errors) / len(errors) if errors else None


def stat_rmse(errors: Sequence[float]) -> Optional[float]:
    return math.sqrt(sum(e * e for e in errors) / len(errors)) if errors else None


def stat_buffer(confidence: float) -> Statistic:
    def f(errors: Sequence[float]) -> Optional[float]:
        return max(0.0, quantile(errors, confidence)) if errors else None
    return f


def bootstrap_interval(
    daily_errors: Mapping[date, Sequence[float]],
    statistic: Statistic,
    level: float = 0.90,
    n_boot: int = 1000,
    seed: int = DEFAULT_SEED,
) -> Interval:
    days = [list(daily_errors[d]) for d in sorted(daily_errors) if daily_errors[d]]
    flat = [e for d in days for e in d]
    point = statistic(flat)
    if len(days) < 2:
        return Interval(point, None, None, level, len(days), 0)
    rng = random.Random(seed)
    draws: list[float] = []
    for _ in range(n_boot):
        sample = rng.choices(days, k=len(days))
        value = statistic([e for d in sample for e in d])
        if value is not None:
            draws.append(value)
    tail = (1.0 - level) / 2.0
    return Interval(point, quantile(draws, tail), quantile(draws, 1.0 - tail), level, len(days), n_boot)