"""Run and cutoff sensitivity: how much does the moment of decision matter?

Re-evaluates the whole window once per candidate cutoff. Which forecast run each cutoff
selects follows from the real publish times, never from an assumed schedule.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Mapping, Optional, Sequence

from .pipeline import evaluate_window, pooled_pairs
from .selection import ForecastBook
from .stats import Metrics, summarize

DEFAULT_SENSITIVITY_CUTOFFS: tuple[time, ...] = (
    time(3, 0), time(5, 0), time(8, 0), time(9, 0), time(10, 0), time(12, 0), time(16, 0),
)


@dataclass(frozen=True)
class CutoffResult:
    cutoff: time
    runs_used: tuple[str, ...]      # distinct UTC clock times of the runs selected, "HH:MM"
    metrics: Metrics
    n_missing_forecast: int


def cutoff_sensitivity(
    book: ForecastBook,
    actuals: Mapping[datetime, float],
    delivery_dates: Sequence[date],
    cutoffs: Sequence[time] = DEFAULT_SENSITIVITY_CUTOFFS,
) -> list[CutoffResult]:
    results: list[CutoffResult] = []
    for c in cutoffs:
        evs = evaluate_window(book, actuals, delivery_dates, c)
        f, a, _ = pooled_pairs(evs)
        runs = sorted({r.strftime("%H:%M") for ev in evs for r in ev.decision.runs_used})
        results.append(CutoffResult(c, tuple(runs), summarize(f, a), sum(e.n_missing_forecast for e in evs)))
    return results


def percent_change(value: Optional[float], reference: Optional[float]) -> Optional[float]:
    """(value - reference) / reference as a fraction. None if either is missing or reference is 0."""
    if value is None or reference is None or reference == 0:
        return None
    return (value - reference) / reference