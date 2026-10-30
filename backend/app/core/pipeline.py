"""Evaluation of one delivery day: selection + alignment + baseline in one place.

This is the data behind the Forecast page, and the building block for every accuracy view.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Iterable, Mapping, Optional

from .alignment import hourly_actual
from .baseline import persistence_baseline
from .selection import DEFAULT_CUTOFF, DecisionForecast, ForecastBook, select_decision_forecast


@dataclass(frozen=True)
class HourPoint:
    target_time: datetime
    forecast_mw: float
    publish_time: datetime
    horizon_h: float
    actual_mw: Optional[float]
    baseline_mw: Optional[float]

    @property
    def error_mw(self) -> Optional[float]:
        """forecast - actual; positive means over-forecast. None if there is no actual."""
        return None if self.actual_mw is None else self.forecast_mw - self.actual_mw


@dataclass(frozen=True)
class DayEvaluation:
    decision: DecisionForecast
    points: tuple[HourPoint, ...]

    @property
    def delivery_date(self) -> date:
        return self.decision.delivery_date

    @property
    def n_missing_forecast(self) -> int:
        return len(self.decision.missing_targets)

    @property
    def n_missing_actual(self) -> int:
        return sum(1 for p in self.points if p.actual_mw is None)

    def scored(self) -> list[HourPoint]:
        """Hours that have both a forecast and an actual."""
        return [p for p in self.points if p.actual_mw is not None]

    def errors(self) -> list[float]:
        return [p.error_mw for p in self.scored()]  # type: ignore[misc]


def evaluate_delivery_day(
    book: ForecastBook,
    actuals: Mapping[datetime, float],
    delivery_date: date,
    cutoff_local: time = DEFAULT_CUTOFF,
) -> DayEvaluation:
    decision = select_decision_forecast(book, delivery_date, cutoff_local)
    points = tuple(
        HourPoint(
            target_time=p.target_time,
            forecast_mw=p.forecast_mw,
            publish_time=p.publish_time,
            horizon_h=p.horizon_h,
            actual_mw=hourly_actual(actuals, p.target_time),
            baseline_mw=persistence_baseline(actuals, p.target_time, decision.cutoff_utc),
        )
        for p in decision.points
    )
    return DayEvaluation(decision=decision, points=points)


def evaluate_window(
    book: ForecastBook,
    actuals: Mapping[datetime, float],
    delivery_dates: Iterable[date],
    cutoff_local: time = DEFAULT_CUTOFF,
) -> list[DayEvaluation]:
    """Evaluate every delivery day in `delivery_dates` with the same cutoff."""
    return [evaluate_delivery_day(book, actuals, d, cutoff_local) for d in delivery_dates]


def daily_errors(evaluations: Iterable[DayEvaluation]) -> dict[date, list[float]]:
    """Signed errors per delivery day (days with no scorable hour are omitted).

    This is the input the expanding-window buffer backtest needs.
    """
    out: dict[date, list[float]] = {}
    for ev in evaluations:
        errs = ev.errors()
        if errs:
            out[ev.delivery_date] = errs
    return out


def pooled_pairs(
    evaluations: Iterable[DayEvaluation], require_baseline: bool = False
) -> tuple[list[float], list[float], list[Optional[float]]]:
    """Forecasts, actuals and baselines for every scored hour, as parallel lists.

    With `require_baseline=True` only hours that also have a baseline are kept, so a model
    and its baseline can be compared on exactly the same hours.
    """
    forecasts: list[float] = []
    actuals: list[float] = []
    baselines: list[Optional[float]] = []
    for ev in evaluations:
        for p in ev.scored():
            if require_baseline and p.baseline_mw is None:
                continue
            forecasts.append(p.forecast_mw)
            actuals.append(p.actual_mw)  # type: ignore[arg-type]
            baselines.append(p.baseline_mw)
    return forecasts, actuals, baselines