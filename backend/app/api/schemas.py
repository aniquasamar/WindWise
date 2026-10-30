"""Response models. They define the OpenAPI contract that the front-end types are generated from.

Every model matches, field for field, a dictionary built in app/services.py.
"""
from datetime import date
from typing import Optional

from pydantic import BaseModel


class HealthOut(BaseModel):
    status: str


class MetricsOut(BaseModel):
    n: int
    bias: Optional[float] = None
    mae: Optional[float] = None
    rmse: Optional[float] = None
    std_error: Optional[float] = None
    mean_actual: Optional[float] = None
    nmae: Optional[float] = None
    nrmse: Optional[float] = None
    wmape: Optional[float] = None
    p50_abs: Optional[float] = None
    p90_abs: Optional[float] = None
    p95_abs: Optional[float] = None
    p10_signed: Optional[float] = None
    p90_signed: Optional[float] = None
    over_share: Optional[float] = None


class RangeOut(BaseModel):
    first: date
    last: date
    n_days: int


# ----------------------------------------------------------------------------- meta
class WindowOut(BaseModel):
    first_decision: date
    last_decision: date
    first_delivery: date
    last_delivery: date


class DefaultsOut(BaseModel):
    cutoff: str
    confidence: float
    min_history_days: int
    benchmark_window_days: int
    benchmark_min_days: int


class AllowedOut(BaseModel):
    confidence: list[float]
    cutoff_min: str
    cutoff_max: str
    cutoff_step_minutes: int


class DataInfoOut(BaseModel):
    source: str
    retrieved_at: str
    data_version: str
    rows_actuals: int
    rows_forecasts: int
    runs: int
    unscheduled_runs: list[str]


class MetaOut(BaseModel):
    window: WindowOut
    defaults: DefaultsOut
    allowed: AllowedOut
    run_times_utc: list[str]
    sign_convention: str
    assumptions: list[str]
    data: DataInfoOut


# ----------------------------------------------------------------------------- forecast page
class RunUsedOut(BaseModel):
    publish_time: str
    age_hours_at_cutoff: float


class PointOut(BaseModel):
    time: str
    forecast_mw: float
    actual_mw: Optional[float] = None
    error_mw: Optional[float] = None
    horizon_h: float
    baseline_mw: Optional[float] = None
    firm_mw: Optional[float] = None
    corrected_mw: Optional[float] = None


class ForecastSummaryOut(BaseModel):
    peak_mw: Optional[float] = None
    mean_mw: Optional[float] = None
    min_mw: Optional[float] = None


class DayBufferOut(BaseModel):
    confidence: float
    buffer_mw: Optional[float] = None
    status: str
    history_days: int
    min_history_days: int


class DayBenchmarkOut(BaseModel):
    method: str
    status: str
    history_days: int
    factor: Optional[float] = None
    notice: str


class ForecastCountsOut(BaseModel):
    hours_total: int
    missing_forecast: int
    missing_actual: int


class ForecastOut(BaseModel):
    delivery_date: date
    decision_date: date
    cutoff_local: str
    cutoff_utc: str
    runs_used: list[RunUsedOut]
    points: list[PointOut]
    forecast_summary: ForecastSummaryOut
    buffer: DayBufferOut
    benchmark: DayBenchmarkOut
    counts: ForecastCountsOut
    day_metrics: Optional[MetricsOut] = None
    sign_convention: str


# ----------------------------------------------------------------------------- accuracy page
class CountsOut(BaseModel):
    hours_scored: int
    missing_forecast: int
    missing_actual: int


class InSampleBufferOut(BaseModel):
    confidence: float
    buffer_mw: Optional[float] = None


class BacktestSummaryOut(BaseModel):
    confidence: float
    min_history_days: int
    days_scored: int
    days_skipped: int
    hours_scored: int
    hours_covered: int
    coverage: Optional[float] = None


class BaselineOut(BaseModel):
    n: int
    description: str
    forecast: MetricsOut
    baseline: MetricsOut
    skill_mae: Optional[float] = None
    skill_rmse: Optional[float] = None


class SummaryOut(BaseModel):
    range: RangeOut
    cutoff: str
    confidence: float
    counts: CountsOut
    metrics: MetricsOut
    buffer_in_sample: InSampleBufferOut
    backtest: BacktestSummaryOut
    baseline: BaselineOut
    insights: list[str]
    sign_convention: str


class IntervalOut(BaseModel):
    point: Optional[float] = None
    low: Optional[float] = None
    high: Optional[float] = None
    level: float
    n_days: int
    n_boot: int


class IntervalsOut(BaseModel):
    range: RangeOut
    cutoff: str
    confidence: float
    method: str
    bias: IntervalOut
    mae: IntervalOut
    rmse: IntervalOut
    buffer: IntervalOut


class HourOut(BaseModel):
    hour: int
    metrics: MetricsOut


class ByHourOut(BaseModel):
    range: RangeOut
    cutoff: str
    hours: list[HourOut]


class DayOut(BaseModel):
    delivery_date: date
    forecast_mean: Optional[float] = None
    actual_mean: Optional[float] = None
    metrics: MetricsOut


class ByDayOut(BaseModel):
    range: RangeOut
    cutoff: str
    days: list[DayOut]


class LevelOut(BaseModel):
    label: str
    forecast_min: float
    forecast_max: float
    metrics: MetricsOut


class ByLevelOut(BaseModel):
    range: RangeOut
    cutoff: str
    note: str
    levels: list[LevelOut]


class HistBinOut(BaseModel):
    lower: float
    upper: float
    count: int


class DistributionOut(BaseModel):
    range: RangeOut
    cutoff: str
    bin_width_mw: float
    n: int
    bins: list[HistBinOut]
    p10: Optional[float] = None
    p50: Optional[float] = None
    p90: Optional[float] = None


class HorizonBucketOut(BaseModel):
    label: str
    lower_h: Optional[float] = None
    upper_h: float
    elapsed: bool
    metrics: MetricsOut


class HorizonOut(BaseModel):
    range: RangeOut
    cutoff: str
    view: str
    bucket_hours: float
    note: str
    buckets: list[HorizonBucketOut]


class CutoffResultOut(BaseModel):
    cutoff: str
    runs_used: list[str]
    n_missing_forecast: int
    metrics: MetricsOut
    mae_change_vs_default: Optional[float] = None
    rmse_change_vs_default: Optional[float] = None


class RunsOut(BaseModel):
    range: RangeOut
    default_cutoff: str
    note: str
    results: list[CutoffResultOut]


class CorrectedOut(BaseModel):
    method: str
    window_days: int
    min_days: int
    days_scored: int
    days_skipped: int
    official: MetricsOut
    corrected: MetricsOut
    rmse_improvement: Optional[float] = None
    mae_improvement: Optional[float] = None


class BenchmarksOut(BaseModel):
    range: RangeOut
    cutoff: str
    baseline: BaselineOut
    experimental_notice: str
    bias_corrected: list[CorrectedOut]


class BacktestDayOut(BaseModel):
    delivery_date: date
    buffer_mw: Optional[float] = None
    history_days: int
    hours: int
    covered: int
    mean_error_mw: Optional[float] = None


class BufferBacktestOut(BaseModel):
    range: RangeOut
    cutoff: str
    confidence: float
    summary: BacktestSummaryOut
    days: list[BacktestDayOut]
    insufficient_history_days: list[date]