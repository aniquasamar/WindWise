"""EXPERIMENTAL benchmark: the decision-time forecast corrected using only past days.

Purpose: show how much of the error is a fixable, systematic offset. It is a yardstick and
an extra, never presented as the official forecast.

No-peeking rule (same as the buffer): for delivery day D, the correction is learned only from
delivery days whose actuals were complete when the decision was made, that is days up to D-2.
It uses the most recent `window_days` of those (default 7) and needs at least `min_days`
(default 3). Days without enough history get no corrected forecast.

Two methods are implemented:
  ratio  : multiply the forecast by  sum(actual) / sum(forecast)  over the history (default,
           because the observed bias grows with wind level);
  offset : subtract the mean error over the history.
Window length and minimum are fixed in advance, not tuned on the results.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import AbstractSet, Iterable, Mapping, Optional, Sequence

from .pipeline import DayEvaluation
from .stats import Metrics, summarize

METHOD_RATIO = "ratio"
METHOD_OFFSET = "offset"
DEFAULT_WINDOW_DAYS = 7
DEFAULT_MIN_DAYS = 3
STATUS_OK = "ok"
STATUS_INSUFFICIENT = "insufficient_history"

DayPairs = Mapping[date, tuple[Sequence[float], Sequence[float]]]   # day -> (forecasts, actuals)


@dataclass(frozen=True)
class Correction:
    method: str
    status: str
    history_days: int
    factor: Optional[float]      # ratio multiplier, or MW to subtract for the offset method

    def apply(self, forecast_mw: float) -> Optional[float]:
        if self.status != STATUS_OK or self.factor is None:
            return None
        if self.method == METHOD_RATIO:
            return forecast_mw * self.factor
        return max(0.0, forecast_mw - self.factor)


def correction_for_day(
    delivery_date: date,
    day_pairs: DayPairs,
    method: str = METHOD_RATIO,
    window_days: int = DEFAULT_WINDOW_DAYS,
    min_days: int = DEFAULT_MIN_DAYS,
) -> Correction:
    if method not in (METHOD_RATIO, METHOD_OFFSET):
        raise ValueError(f"unknown method {method!r}")
    last_usable = delivery_date - timedelta(days=2)
    days = sorted(d for d, (f, _a) in day_pairs.items() if d <= last_usable and len(f) > 0)
    recent = days[-window_days:]
    if len(recent) < min_days:
        return Correction(method, STATUS_INSUFFICIENT, len(recent), None)

    sum_f = sum(sum(day_pairs[d][0]) for d in recent)
    sum_a = sum(sum(day_pairs[d][1]) for d in recent)
    n = sum(len(day_pairs[d][0]) for d in recent)
    if method == METHOD_RATIO:
        if sum_f <= 0:
            return Correction(method, STATUS_INSUFFICIENT, len(recent), None)
        return Correction(method, STATUS_OK, len(recent), sum_a / sum_f)
    return Correction(method, STATUS_OK, len(recent), (sum_f - sum_a) / n)


@dataclass(frozen=True)
class BenchmarkComparison:
    method: str
    window_days: int
    min_days: int
    days_scored: int
    days_skipped: int
    raw: Metrics                 # the official decision-time forecast, on the SAME hours
    corrected: Metrics
    corrections: tuple[tuple[date, Correction], ...]


def day_pairs_from(evaluations: Iterable[DayEvaluation]) -> dict[date, tuple[list[float], list[float]]]:
    out: dict[date, tuple[list[float], list[float]]] = {}
    for ev in evaluations:
        pts = ev.scored()
        if pts:
            out[ev.delivery_date] = ([p.forecast_mw for p in pts], [p.actual_mw for p in pts])  # type: ignore[misc]
    return out


def evaluate_benchmark(
    evaluations: Sequence[DayEvaluation],
    method: str = METHOD_RATIO,
    window_days: int = DEFAULT_WINDOW_DAYS,
    min_days: int = DEFAULT_MIN_DAYS,
    score_dates: Optional[AbstractSet[date]] = None,
) -> BenchmarkComparison:
    """Corrections always learn from ALL earlier days in `evaluations`; if `score_dates` is given,
    only those days are scored (so a date-range view still has its history)."""
    pairs = day_pairs_from(evaluations)
    raw_f: list[float] = []
    cor_f: list[float] = []
    acts: list[float] = []
    corrections: list[tuple[date, Correction]] = []
    scored = skipped = 0
    for ev in sorted(evaluations, key=lambda e: e.delivery_date):
        pts = ev.scored()
        if not pts:
            continue
        corr = correction_for_day(ev.delivery_date, pairs, method, window_days, min_days)
        corrections.append((ev.delivery_date, corr))
        if score_dates is not None and ev.delivery_date not in score_dates:
            continue
        if corr.status != STATUS_OK:
            skipped += 1
            continue
        scored += 1
        for p in pts:
            raw_f.append(p.forecast_mw)
            cor_f.append(corr.apply(p.forecast_mw))  # type: ignore[arg-type]
            acts.append(p.actual_mw)                 # type: ignore[arg-type]
    return BenchmarkComparison(
        method, window_days, min_days, scored, skipped,
        summarize(raw_f, acts), summarize(cor_f, acts), tuple(corrections),
    )