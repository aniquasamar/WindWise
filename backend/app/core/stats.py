"""Summary statistics for forecast errors.

Convention used everywhere: error = forecast - actual, in MW.
Positive error means the forecast was too high (over-forecast).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence


def quantile(values: Sequence[float], q: float) -> float:
    """Empirical quantile with linear interpolation between order statistics.

    This is the common default (often called "type 7"): position = (n - 1) * q.
    """
    if not values:
        raise ValueError("quantile of an empty sequence")
    if not 0.0 <= q <= 1.0:
        raise ValueError("q must be between 0 and 1")
    xs = sorted(values)
    pos = (len(xs) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return float(xs[lo])
    return float(xs[lo] + (xs[hi] - xs[lo]) * (pos - lo))


@dataclass(frozen=True)
class Metrics:
    """Headline accuracy numbers. All MW values are plain MW; ratios are fractions."""

    n: int
    bias: Optional[float] = None          # mean error: positive = forecast too high
    mae: Optional[float] = None           # mean absolute error
    rmse: Optional[float] = None          # root mean squared error
    std_error: Optional[float] = None     # spread of errors around the bias
    mean_actual: Optional[float] = None
    nmae: Optional[float] = None          # MAE / mean actual
    nrmse: Optional[float] = None         # RMSE / mean actual
    wmape: Optional[float] = None         # sum |error| / sum actual
    p50_abs: Optional[float] = None
    p90_abs: Optional[float] = None
    p95_abs: Optional[float] = None
    p10_signed: Optional[float] = None    # lower tail of signed error (under-forecast side)
    p90_signed: Optional[float] = None    # upper tail of signed error (over-forecast side)
    over_share: Optional[float] = None    # share of hours with error > 0


def summarize(forecasts: Sequence[float], actuals: Sequence[float]) -> Metrics:
    """Metrics for paired forecasts and actuals (same length, same order)."""
    if len(forecasts) != len(actuals):
        raise ValueError("forecasts and actuals must have the same length")
    n = len(forecasts)
    if n == 0:
        return Metrics(n=0)

    errors = [f - a for f, a in zip(forecasts, actuals)]
    abs_errors = [abs(e) for e in errors]
    bias = sum(errors) / n
    mae = sum(abs_errors) / n
    rmse = math.sqrt(sum(e * e for e in errors) / n)
    std_error = math.sqrt(sum((e - bias) ** 2 for e in errors) / n)
    mean_actual = sum(actuals) / n
    sum_actual = sum(actuals)

    return Metrics(
        n=n,
        bias=bias,
        mae=mae,
        rmse=rmse,
        std_error=std_error,
        mean_actual=mean_actual,
        nmae=mae / mean_actual if mean_actual > 0 else None,
        nrmse=rmse / mean_actual if mean_actual > 0 else None,
        wmape=sum(abs_errors) / sum_actual if sum_actual > 0 else None,
        p50_abs=quantile(abs_errors, 0.50),
        p90_abs=quantile(abs_errors, 0.90),
        p95_abs=quantile(abs_errors, 0.95),
        p10_signed=quantile(errors, 0.10),
        p90_signed=quantile(errors, 0.90),
        over_share=sum(1 for e in errors if e > 0) / n,
    )


def skill_score(model_error: Optional[float], baseline_error: Optional[float]) -> Optional[float]:
    """1 - model/baseline. Positive means better than the baseline; 0 means no better."""
    if model_error is None or baseline_error is None or baseline_error == 0:
        return None
    return 1.0 - model_error / baseline_error