"""Plain-language insight sentences, generated from fixed templates.

Deterministic: the same numbers always give the same sentences, so they can be tested.
Any sentence whose inputs are missing is skipped rather than guessed.
"""
from __future__ import annotations

from datetime import date
from typing import Optional, Sequence

from .breakdowns import DaySummary
from .buffer import BacktestResult
from .stats import Metrics


def _mw(x: float) -> str:
    return f"{round(x):,}"


def _day(d: date) -> str:
    return f"{d.day} {d.strftime('%b')}"


def generate_insights(
    metrics: Metrics,
    day_summaries: Sequence[DaySummary],
    in_sample_buffer: Optional[float],
    confidence: float,
    backtest: Optional[BacktestResult] = None,
) -> list[str]:
    out: list[str] = []
    pct = f"{round(confidence * 100)}%"

    scored_days = [d for d in day_summaries if d.metrics.bias is not None]
    if metrics.n and metrics.over_share is not None and metrics.bias is not None and scored_days:
        above = sum(1 for d in scored_days if d.metrics.bias > 0)
        sentence = (
            f"The forecast was above actual wind in {metrics.over_share:.0%} of hours and on "
            f"{above} of {len(scored_days)} days, with a mean error of {metrics.bias:+,.0f} MW"
        )
        if metrics.mean_actual:
            sentence += f" ({metrics.bias / metrics.mean_actual:+.0%} of mean wind)"
        out.append(sentence + ".")

    if metrics.mae is not None and metrics.p90_abs is not None:
        s = f"A typical miss is {_mw(metrics.mae)} MW"
        if metrics.nmae is not None:
            s += f" ({metrics.nmae:.0%} of mean wind)"
        out.append(s + f"; one hour in ten is off by more than {_mw(metrics.p90_abs)} MW.")

    if scored_days:
        worst = max(scored_days, key=lambda d: abs(d.metrics.bias))  # type: ignore[arg-type]
        direction = "above" if worst.metrics.bias > 0 else "below"       # type: ignore[operator]
        out.append(
            f"Largest daily miss: {_day(worst.delivery_date)}, when the forecast averaged "
            f"{_mw(abs(worst.metrics.bias))} MW {direction} actual wind."  # type: ignore[arg-type]
        )

    if in_sample_buffer is not None:
        out.append(
            f"With hindsight, planning on forecast minus {_mw(in_sample_buffer)} MW would have "
            f"been covered in {pct} of hours."
        )
    if backtest is not None and backtest.coverage is not None:
        out.append(
            f"Applied day by day using only earlier data, the {pct} buffer held in "
            f"{backtest.coverage:.1%} of hours."
        )
    return out