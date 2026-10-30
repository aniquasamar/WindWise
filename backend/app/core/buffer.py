"""The buffer ("so what") and its honest backtest.

Costly risk assumed: the forecast promises more wind than arrives, so the buyer must cover
the shortfall late. (We have no price data, so this direction is an assumption that the
app states openly.)

    buffer    = max(0, P_c of signed error)        error = forecast - actual
    firm wind = max(0, forecast - buffer)

If error <= buffer in a share c of hours, actual wind was at least `firm wind` in that
share of hours.

Backtest rule (no peeking): the buffer used for delivery day D is computed only from
delivery days whose actuals were complete when the decision for D was made, that is days
up to D-2. Days with too little history get no buffer ("insufficient history").
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Mapping, Optional, Sequence

from .stats import quantile

DEFAULT_CONFIDENCE = 0.90
DEFAULT_MIN_HISTORY_DAYS = 7
STATUS_OK = "ok"
STATUS_INSUFFICIENT = "insufficient_history"


def buffer_from_errors(errors: Sequence[float], confidence: float = DEFAULT_CONFIDENCE) -> Optional[float]:
    if not errors:
        return None
    return max(0.0, quantile(errors, confidence))


def firm_wind(forecast_mw: float, buffer_mw: float) -> float:
    return max(0.0, forecast_mw - buffer_mw)


@dataclass(frozen=True)
class BufferResult:
    buffer_mw: Optional[float]
    status: str
    history_days: int
    confidence: float


def history_errors(delivery_date: date, daily_errors: Mapping[date, Sequence[float]]) -> tuple[list[float], int]:
    """Errors from delivery days complete at the decision time (days <= D-2) and how many days."""
    last_usable = delivery_date - timedelta(days=2)
    errors: list[float] = []
    days = 0
    for d, errs in daily_errors.items():
        if d <= last_usable and len(errs) > 0:
            errors.extend(errs)
            days += 1
    return errors, days


def expanding_buffer(
    delivery_date: date,
    daily_errors: Mapping[date, Sequence[float]],
    confidence: float = DEFAULT_CONFIDENCE,
    min_days: int = DEFAULT_MIN_HISTORY_DAYS,
) -> BufferResult:
    errors, days = history_errors(delivery_date, daily_errors)
    if days < min_days:
        return BufferResult(None, STATUS_INSUFFICIENT, days, confidence)
    return BufferResult(buffer_from_errors(errors, confidence), STATUS_OK, days, confidence)


@dataclass(frozen=True)
class BacktestDay:
    delivery_date: date
    buffer_mw: float
    history_days: int
    hours: int
    covered: int

    @property
    def coverage(self) -> float:
        return self.covered / self.hours if self.hours else float("nan")


@dataclass(frozen=True)
class BacktestResult:
    confidence: float
    min_days: int
    days: tuple[BacktestDay, ...]
    days_skipped: int

    @property
    def hours_scored(self) -> int:
        return sum(d.hours for d in self.days)

    @property
    def hours_covered(self) -> int:
        return sum(d.covered for d in self.days)

    @property
    def coverage(self) -> Optional[float]:
        """Share of scored hours where actual wind was at least forecast minus buffer."""
        h = self.hours_scored
        return self.hours_covered / h if h else None


def backtest_buffer(
    daily_errors: Mapping[date, Sequence[float]],
    confidence: float = DEFAULT_CONFIDENCE,
    min_days: int = DEFAULT_MIN_HISTORY_DAYS,
) -> BacktestResult:
    """Apply the expanding-window buffer day by day and measure how often it held."""
    days: list[BacktestDay] = []
    skipped = 0
    for d in sorted(daily_errors):
        errs = daily_errors[d]
        if not errs:
            continue
        res = expanding_buffer(d, daily_errors, confidence, min_days)
        if res.status != STATUS_OK or res.buffer_mw is None:
            skipped += 1
            continue
        covered = sum(1 for e in errs if e <= res.buffer_mw)
        days.append(BacktestDay(d, res.buffer_mw, res.history_days, len(errs), covered))
    return BacktestResult(confidence, min_days, tuple(days), skipped)