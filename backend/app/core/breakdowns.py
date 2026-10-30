"""Accuracy broken down by hour of day, by delivery day, by forecast level, and as a histogram.

All breakdowns use decision-time forecasts (see selection.py) and the standard sign
convention: error = forecast - actual.

"Forecast level" groups hours by the size of the FORECAST, which is known at decision time.
Grouping by the actual would be misleading: picking hours because their outcome was low or
high manufactures patterns that nobody could act on.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Optional, Sequence

from .pipeline import DayEvaluation, HourPoint
from .stats import Metrics, quantile, summarize
from .timeutils import LONDON


def _scored_points(evaluations: Iterable[DayEvaluation]) -> list[HourPoint]:
    return [p for ev in evaluations for p in ev.scored()]


def _metrics_for(points: Sequence[HourPoint]) -> Metrics:
    return summarize([p.forecast_mw for p in points], [p.actual_mw for p in points])  # type: ignore[misc]


@dataclass(frozen=True)
class HourMetrics:
    hour: int          # UK local hour of day, 0-23
    metrics: Metrics


def by_hour_of_day(evaluations: Iterable[DayEvaluation]) -> list[HourMetrics]:
    groups: dict[int, list[HourPoint]] = defaultdict(list)
    for p in _scored_points(evaluations):
        groups[p.target_time.astimezone(LONDON).hour].append(p)
    return [HourMetrics(h, _metrics_for(groups[h])) for h in sorted(groups)]


@dataclass(frozen=True)
class DaySummary:
    delivery_date: date
    forecast_mean: Optional[float]
    actual_mean: Optional[float]
    metrics: Metrics


def by_day(evaluations: Iterable[DayEvaluation]) -> list[DaySummary]:
    out: list[DaySummary] = []
    for ev in sorted(evaluations, key=lambda e: e.delivery_date):
        pts = ev.scored()
        m = _metrics_for(pts)
        fmean = sum(p.forecast_mw for p in pts) / len(pts) if pts else None
        out.append(DaySummary(ev.delivery_date, fmean, m.mean_actual, m))
    return out


@dataclass(frozen=True)
class LevelMetrics:
    label: str                 # "low", "medium" or "high"
    forecast_min: float
    forecast_max: float
    metrics: Metrics


def by_forecast_level(evaluations: Iterable[DayEvaluation]) -> list[LevelMetrics]:
    """Terciles of the forecast value across the window. Empty if there are too few hours."""
    pts = _scored_points(evaluations)
    if len(pts) < 3:
        return []
    forecasts = [p.forecast_mw for p in pts]
    c1, c2 = quantile(forecasts, 1 / 3), quantile(forecasts, 2 / 3)
    groups: dict[str, list[HourPoint]] = {"low": [], "medium": [], "high": []}
    for p in pts:
        key = "low" if p.forecast_mw <= c1 else "medium" if p.forecast_mw <= c2 else "high"
        groups[key].append(p)
    out: list[LevelMetrics] = []
    for label in ("low", "medium", "high"):
        g = groups[label]
        if g:
            fs = [p.forecast_mw for p in g]
            out.append(LevelMetrics(label, min(fs), max(fs), _metrics_for(g)))
    return out


@dataclass(frozen=True)
class HistogramBin:
    lower: float
    upper: float
    count: int


def error_histogram(errors: Sequence[float], bin_width: float = 500.0) -> list[HistogramBin]:
    """Counts of signed errors in equal-width bins aligned to multiples of `bin_width`."""
    if bin_width <= 0:
        raise ValueError("bin_width must be positive")
    if not errors:
        return []
    lo = math.floor(min(errors) / bin_width) * bin_width
    hi = math.floor(max(errors) / bin_width) * bin_width + bin_width
    n_bins = int(round((hi - lo) / bin_width))
    counts = [0] * n_bins
    for e in errors:
        counts[min(int(math.floor((e - lo) / bin_width)), n_bins - 1)] += 1
    return [HistogramBin(lo + i * bin_width, lo + (i + 1) * bin_width, c) for i, c in enumerate(counts)]