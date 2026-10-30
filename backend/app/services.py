"""Application services: turn core results into JSON-ready dictionaries.

Framework-free on purpose. The web layer only validates requests and returns what these
methods produce, so every number the API serves can be unit-tested without a web server.

Rounding happens here, once: MW to 1 decimal place, ratios and shares to 4.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any, Optional, Sequence

from app.core.benchmark import (
    DEFAULT_MIN_DAYS as BENCH_MIN_DAYS,
    DEFAULT_WINDOW_DAYS as BENCH_WINDOW_DAYS,
    METHOD_OFFSET,
    METHOD_RATIO,
    correction_for_day,
    day_pairs_from,
    evaluate_benchmark,
)
from app.core.breakdowns import by_day, by_forecast_level, by_hour_of_day, error_histogram
from app.core.buffer import (
    DEFAULT_MIN_HISTORY_DAYS,
    BacktestResult,
    backtest_buffer,
    buffer_from_errors,
    expanding_buffer,
    firm_wind,
)
from app.core.horizon import decision_time_horizon, full_horizon_curve
from app.core.insights import generate_insights
from app.core.pipeline import DayEvaluation, daily_errors, evaluate_window, pooled_pairs
from app.core.runs import DEFAULT_SENSITIVITY_CUTOFFS, cutoff_sensitivity, percent_change
from app.core.stats import Metrics, quantile, skill_score, summarize
from app.core.uncertainty import bootstrap_interval, stat_bias, stat_buffer, stat_mae, stat_rmse
from app.repository.sqlite_repo import Dataset
from app.scope import FIRST_DECISION, FIRST_DELIVERY, LAST_DECISION, LAST_DELIVERY, delivery_days
from app.validation import (
    ALLOWED_CONFIDENCE,
    CUTOFF_MAX,
    CUTOFF_MIN,
    CUTOFF_STEP_MINUTES,
    DEFAULT_CONFIDENCE,
    DEFAULT_CUTOFF,
)

SIGN_CONVENTION = "error = forecast - actual; a positive error means the forecast was too high"
HISTOGRAM_BIN_MW = 500.0
BOOTSTRAP_DRAWS = 1000

ASSUMPTIONS = [
    "Decisions are made on 1 to 31 January 2026 at the cutoff time (default 09:00 UK time) and cover "
    "delivery on the following day, 2 January to 1 February 2026.",
    "The decision-time forecast is the latest WINDFOR run published at or before the cutoff. "
    "Later runs are never used, and a missing hour is never filled from a later run.",
    "Forecasts are hourly. Each is compared with the mean of the two half-hourly FUELHH wind actuals in that hour.",
    SIGN_CONVENTION[0].upper() + SIGN_CONVENTION[1:] + ".",
    "The buffer assumes the costly risk is wind falling short of the forecast. No price or demand data is used.",
    "Backtests use only information available at decision time: earlier delivery days whose actuals were complete.",
    "The cause of the persistent over-forecast cannot be established from this data. It may reflect "
    "differences in what the two series cover.",
]

EXPERIMENTAL_NOTICE = (
    "Experimental benchmark: the forecast corrected using only past days. It is a yardstick for how much "
    "of the error is systematic. It is not the official forecast."
)
HORIZON_NOTES = {
    "decision": (
        "Only the forecast the buyer used. Because a single run is used for the whole delivery day, horizon "
        "and time of day move together here, so this view cannot separate the two."
    ),
    "full": (
        "Every published run for every target hour, from days ahead to targets already elapsed when the run "
        "was published. Descriptive context, not what the buyer saw. Samples overlap heavily."
    ),
}


# ----------------------------------------------------------------------------- helpers
def rnd(x: Optional[float], digits: int = 1) -> Optional[float]:
    return None if x is None else round(float(x), digits)


def iso_z(d: datetime) -> str:
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def metrics_dict(m: Metrics) -> dict[str, Any]:
    return {
        "n": m.n,
        "bias": rnd(m.bias),
        "mae": rnd(m.mae),
        "rmse": rnd(m.rmse),
        "std_error": rnd(m.std_error),
        "mean_actual": rnd(m.mean_actual),
        "nmae": rnd(m.nmae, 4),
        "nrmse": rnd(m.nrmse, 4),
        "wmape": rnd(m.wmape, 4),
        "p50_abs": rnd(m.p50_abs),
        "p90_abs": rnd(m.p90_abs),
        "p95_abs": rnd(m.p95_abs),
        "p10_signed": rnd(m.p10_signed),
        "p90_signed": rnd(m.p90_signed),
        "over_share": rnd(m.over_share, 4),
    }


def _hhmm(t: time) -> str:
    return t.strftime("%H:%M")


class AnalyticsService:
    def __init__(self, dataset: Dataset) -> None:
        self.ds = dataset
        self._days = tuple(delivery_days())
        self._eval_cache: dict[time, tuple[DayEvaluation, ...]] = {}

    # ------------------------------------------------------------------ shared building blocks
    def evaluations(self, cutoff: time) -> tuple[DayEvaluation, ...]:
        """Every delivery day in the project window, evaluated at one cutoff (cached)."""
        cached = self._eval_cache.get(cutoff)
        if cached is None:
            cached = tuple(evaluate_window(self.ds.book, self.ds.actuals, self._days, cutoff))
            self._eval_cache[cutoff] = cached
        return cached

    def _select(self, cutoff: time, first: date, last: date) -> list[DayEvaluation]:
        return [e for e in self.evaluations(cutoff) if first <= e.delivery_date <= last]

    @staticmethod
    def _range(first: date, last: date) -> dict[str, Any]:
        return {"first": first, "last": last, "n_days": (last - first).days + 1}

    @staticmethod
    def _counts(sel: Sequence[DayEvaluation]) -> dict[str, int]:
        return {
            "hours_scored": sum(len(e.scored()) for e in sel),
            "missing_forecast": sum(e.n_missing_forecast for e in sel),
            "missing_actual": sum(e.n_missing_actual for e in sel),
        }

    def _backtest_for_range(
        self, cutoff: time, confidence: float, first: date, last: date
    ) -> tuple[BacktestResult, list[date]]:
        """Expanding-window backtest using ALL earlier days as history, scored on the selected days."""
        all_evs = self.evaluations(cutoff)
        daily_all = daily_errors(all_evs)
        full = backtest_buffer(daily_all, confidence, DEFAULT_MIN_HISTORY_DAYS)
        scored_days = tuple(d for d in full.days if first <= d.delivery_date <= last)
        in_range_with_errors = [d for d in daily_all if first <= d <= last]
        scored_dates = {d.delivery_date for d in scored_days}
        insufficient = sorted(d for d in in_range_with_errors if d not in scored_dates)
        return BacktestResult(confidence, DEFAULT_MIN_HISTORY_DAYS, scored_days, len(insufficient)), insufficient

    @staticmethod
    def _backtest_dict(bt: BacktestResult) -> dict[str, Any]:
        return {
            "confidence": bt.confidence,
            "min_history_days": bt.min_days,
            "days_scored": len(bt.days),
            "days_skipped": bt.days_skipped,
            "hours_scored": bt.hours_scored,
            "hours_covered": bt.hours_covered,
            "coverage": rnd(bt.coverage, 4),
        }

    def _baseline_block(self, sel: Sequence[DayEvaluation]) -> dict[str, Any]:
        f, a, b = pooled_pairs(sel, require_baseline=True)
        mf = summarize(f, a)
        mb = summarize([x for x in b if x is not None], a)
        return {
            "n": mf.n,
            "description": "Actual wind for the same hour 48 hours earlier (the latest complete day at decision time)",
            "forecast": metrics_dict(mf),
            "baseline": metrics_dict(mb),
            "skill_mae": rnd(skill_score(mf.mae, mb.mae), 4),
            "skill_rmse": rnd(skill_score(mf.rmse, mb.rmse), 4),
        }

    # ------------------------------------------------------------------ endpoints
    def meta(self) -> dict[str, Any]:
        m = self.ds.meta
        unscheduled = [x for x in m.get("unscheduled_runs", "").split(",") if x]
        return {
            "window": {
                "first_decision": FIRST_DECISION,
                "last_decision": LAST_DECISION,
                "first_delivery": FIRST_DELIVERY,
                "last_delivery": LAST_DELIVERY,
            },
            "defaults": {
                "cutoff": _hhmm(DEFAULT_CUTOFF),
                "confidence": DEFAULT_CONFIDENCE,
                "min_history_days": DEFAULT_MIN_HISTORY_DAYS,
                "benchmark_window_days": BENCH_WINDOW_DAYS,
                "benchmark_min_days": BENCH_MIN_DAYS,
            },
            "allowed": {
                "confidence": list(ALLOWED_CONFIDENCE),
                "cutoff_min": _hhmm(CUTOFF_MIN),
                "cutoff_max": _hhmm(CUTOFF_MAX),
                "cutoff_step_minutes": CUTOFF_STEP_MINUTES,
            },
            "run_times_utc": sorted({t.strftime("%H:%M") for t in self.ds.book.publish_times()}),
            "sign_convention": SIGN_CONVENTION,
            "assumptions": ASSUMPTIONS,
            "data": {
                "source": m.get("source", ""),
                "retrieved_at": m.get("retrieved_at", ""),
                "data_version": m.get("data_version", ""),
                "rows_actuals": int(m.get("rows_actuals", 0)),
                "rows_forecasts": int(m.get("rows_forecasts", 0)),
                "runs": int(m.get("runs", 0)),
                "unscheduled_runs": unscheduled,
            },
        }

    def forecast(self, delivery_date: date, cutoff: time, confidence: float) -> dict[str, Any]:
        evs = self.evaluations(cutoff)
        ev = next(e for e in evs if e.delivery_date == delivery_date)
        buf = expanding_buffer(delivery_date, daily_errors(evs), confidence, DEFAULT_MIN_HISTORY_DAYS)
        corr = correction_for_day(delivery_date, day_pairs_from(evs), METHOD_RATIO, BENCH_WINDOW_DAYS, BENCH_MIN_DAYS)

        points = []
        for p in ev.points:
            points.append(
                {
                    "time": iso_z(p.target_time),
                    "forecast_mw": rnd(p.forecast_mw),
                    "actual_mw": rnd(p.actual_mw),
                    "error_mw": rnd(p.error_mw),
                    "horizon_h": rnd(p.horizon_h, 2),
                    "baseline_mw": rnd(p.baseline_mw),
                    "firm_mw": None if buf.buffer_mw is None else rnd(firm_wind(p.forecast_mw, buf.buffer_mw)),
                    "corrected_mw": rnd(corr.apply(p.forecast_mw)),
                }
            )

        forecasts = [p.forecast_mw for p in ev.points]
        scored = ev.scored()
        day_metrics = (
            metrics_dict(summarize([p.forecast_mw for p in scored], [p.actual_mw for p in scored]))  # type: ignore[misc]
            if scored
            else None
        )
        return {
            "delivery_date": delivery_date,
            "decision_date": ev.decision.decision_date,
            "cutoff_local": _hhmm(cutoff),
            "cutoff_utc": iso_z(ev.decision.cutoff_utc),
            "runs_used": [
                {
                    "publish_time": iso_z(r),
                    "age_hours_at_cutoff": rnd((ev.decision.cutoff_utc - r).total_seconds() / 3600.0, 2),
                }
                for r in ev.decision.runs_used
            ],
            "points": points,
            "forecast_summary": {
                "peak_mw": rnd(max(forecasts)) if forecasts else None,
                "mean_mw": rnd(sum(forecasts) / len(forecasts)) if forecasts else None,
                "min_mw": rnd(min(forecasts)) if forecasts else None,
            },
            "buffer": {
                "confidence": confidence,
                "buffer_mw": rnd(buf.buffer_mw),
                "status": buf.status,
                "history_days": buf.history_days,
                "min_history_days": DEFAULT_MIN_HISTORY_DAYS,
            },
            "benchmark": {
                "method": corr.method,
                "status": corr.status,
                "history_days": corr.history_days,
                "factor": rnd(corr.factor, 4),
                "notice": EXPERIMENTAL_NOTICE,
            },
            "counts": {
                "hours_total": len(ev.points) + ev.n_missing_forecast,
                "missing_forecast": ev.n_missing_forecast,
                "missing_actual": ev.n_missing_actual,
            },
            "day_metrics": day_metrics,
            "sign_convention": SIGN_CONVENTION,
        }

    def summary(self, first: date, last: date, cutoff: time, confidence: float) -> dict[str, Any]:
        sel = self._select(cutoff, first, last)
        f, a, _ = pooled_pairs(sel)
        metrics = summarize(f, a)
        errs = [e for ev in sel for e in ev.errors()]
        buffer_in_sample = buffer_from_errors(errs, confidence)
        bt, _insufficient = self._backtest_for_range(cutoff, confidence, first, last)
        return {
            "range": self._range(first, last),
            "cutoff": _hhmm(cutoff),
            "confidence": confidence,
            "counts": self._counts(sel),
            "metrics": metrics_dict(metrics),
            "buffer_in_sample": {"confidence": confidence, "buffer_mw": rnd(buffer_in_sample)},
            "backtest": self._backtest_dict(bt),
            "baseline": self._baseline_block(sel),
            "insights": generate_insights(metrics, by_day(sel), buffer_in_sample, confidence, bt),
            "sign_convention": SIGN_CONVENTION,
        }

    def intervals(self, first: date, last: date, cutoff: time, confidence: float) -> dict[str, Any]:
        daily = daily_errors(self._select(cutoff, first, last))

        def block(stat) -> dict[str, Any]:
            iv = bootstrap_interval(daily, stat, level=0.90, n_boot=BOOTSTRAP_DRAWS)
            return {
                "point": rnd(iv.point),
                "low": rnd(iv.low),
                "high": rnd(iv.high),
                "level": iv.level,
                "n_days": iv.n_days,
                "n_boot": iv.n_boot,
            }

        return {
            "range": self._range(first, last),
            "cutoff": _hhmm(cutoff),
            "confidence": confidence,
            "method": "day-block bootstrap: whole delivery days are resampled with replacement (fixed seed)",
            "bias": block(stat_bias),
            "mae": block(stat_mae),
            "rmse": block(stat_rmse),
            "buffer": block(stat_buffer(confidence)),
        }

    def by_hour(self, first: date, last: date, cutoff: time) -> dict[str, Any]:
        sel = self._select(cutoff, first, last)
        return {
            "range": self._range(first, last),
            "cutoff": _hhmm(cutoff),
            "hours": [{"hour": h.hour, "metrics": metrics_dict(h.metrics)} for h in by_hour_of_day(sel)],
        }

    def by_day(self, first: date, last: date, cutoff: time) -> dict[str, Any]:
        sel = self._select(cutoff, first, last)
        return {
            "range": self._range(first, last),
            "cutoff": _hhmm(cutoff),
            "days": [
                {
                    "delivery_date": d.delivery_date,
                    "forecast_mean": rnd(d.forecast_mean),
                    "actual_mean": rnd(d.actual_mean),
                    "metrics": metrics_dict(d.metrics),
                }
                for d in by_day(sel)
            ],
        }

    def by_forecast_level(self, first: date, last: date, cutoff: time) -> dict[str, Any]:
        sel = self._select(cutoff, first, last)
        return {
            "range": self._range(first, last),
            "cutoff": _hhmm(cutoff),
            "note": "Hours are grouped by the size of the forecast (terciles), which is known at decision time.",
            "levels": [
                {
                    "label": lv.label,
                    "forecast_min": rnd(lv.forecast_min),
                    "forecast_max": rnd(lv.forecast_max),
                    "metrics": metrics_dict(lv.metrics),
                }
                for lv in by_forecast_level(sel)
            ],
        }

    def distribution(self, first: date, last: date, cutoff: time) -> dict[str, Any]:
        sel = self._select(cutoff, first, last)
        errs = [e for ev in sel for e in ev.errors()]
        return {
            "range": self._range(first, last),
            "cutoff": _hhmm(cutoff),
            "bin_width_mw": HISTOGRAM_BIN_MW,
            "n": len(errs),
            "bins": [
                {"lower": b.lower, "upper": b.upper, "count": b.count}
                for b in error_histogram(errs, HISTOGRAM_BIN_MW)
            ],
            "p10": rnd(quantile(errs, 0.10)) if errs else None,
            "p50": rnd(quantile(errs, 0.50)) if errs else None,
            "p90": rnd(quantile(errs, 0.90)) if errs else None,
        }

    def horizon(self, first: date, last: date, cutoff: time, view: str) -> dict[str, Any]:
        sel = self._select(cutoff, first, last)
        if view == "decision":
            width = 6.0
            buckets = decision_time_horizon(sel, width)
        else:
            width = 12.0
            days = [e.delivery_date for e in sel]
            buckets = full_horizon_curve(self.ds.book, self.ds.actuals, days, width)
        return {
            "range": self._range(first, last),
            "cutoff": _hhmm(cutoff),
            "view": view,
            "bucket_hours": width,
            "note": HORIZON_NOTES[view],
            "buckets": [
                {
                    "label": b.label,
                    "lower_h": None if b.elapsed else b.lower_h,
                    "upper_h": b.upper_h,
                    "elapsed": b.elapsed,
                    "metrics": metrics_dict(b.metrics),
                }
                for b in buckets
            ],
        }

    def runs(self, first: date, last: date) -> dict[str, Any]:
        days = [d for d in self._days if first <= d <= last]
        results = cutoff_sensitivity(self.ds.book, self.ds.actuals, days, DEFAULT_SENSITIVITY_CUTOFFS)
        ref = next((r for r in results if r.cutoff == DEFAULT_CUTOFF), None)
        return {
            "range": self._range(first, last),
            "default_cutoff": _hhmm(DEFAULT_CUTOFF),
            "note": "Each cutoff selects whichever run was published last before it. Check which runs are "
            "available before the relevant auction closes.",
            "results": [
                {
                    "cutoff": _hhmm(r.cutoff),
                    "runs_used": list(r.runs_used),
                    "n_missing_forecast": r.n_missing_forecast,
                    "metrics": metrics_dict(r.metrics),
                    "mae_change_vs_default": rnd(percent_change(r.metrics.mae, ref.metrics.mae if ref else None), 4),
                    "rmse_change_vs_default": rnd(percent_change(r.metrics.rmse, ref.metrics.rmse if ref else None), 4),
                }
                for r in results
            ],
        }

    def benchmarks(self, first: date, last: date, cutoff: time) -> dict[str, Any]:
        sel = self._select(cutoff, first, last)
        score_dates = {e.delivery_date for e in sel}
        corrected = []
        for method in (METHOD_RATIO, METHOD_OFFSET):
            r = evaluate_benchmark(self.evaluations(cutoff), method, BENCH_WINDOW_DAYS, BENCH_MIN_DAYS, score_dates)
            corrected.append(
                {
                    "method": r.method,
                    "window_days": r.window_days,
                    "min_days": r.min_days,
                    "days_scored": r.days_scored,
                    "days_skipped": r.days_skipped,
                    "official": metrics_dict(r.raw),
                    "corrected": metrics_dict(r.corrected),
                    "rmse_improvement": rnd(skill_score(r.corrected.rmse, r.raw.rmse), 4),
                    "mae_improvement": rnd(skill_score(r.corrected.mae, r.raw.mae), 4),
                }
            )
        return {
            "range": self._range(first, last),
            "cutoff": _hhmm(cutoff),
            "baseline": self._baseline_block(sel),
            "experimental_notice": EXPERIMENTAL_NOTICE,
            "bias_corrected": corrected,
        }

    def buffer_backtest(self, first: date, last: date, cutoff: time, confidence: float) -> dict[str, Any]:
        bt, insufficient = self._backtest_for_range(cutoff, confidence, first, last)
        daily_means = {d.delivery_date: d.metrics.bias for d in by_day(self._select(cutoff, first, last))}
        return {
            "range": self._range(first, last),
            "cutoff": _hhmm(cutoff),
            "confidence": confidence,
            "summary": self._backtest_dict(bt),
            "days": [
                {
                    "delivery_date": d.delivery_date,
                    "buffer_mw": rnd(d.buffer_mw),
                    "history_days": d.history_days,
                    "hours": d.hours,
                    "covered": d.covered,
                    "mean_error_mw": rnd(daily_means.get(d.delivery_date)),
                }
                for d in bt.days
            ],
            "insufficient_history_days": insufficient,
        }