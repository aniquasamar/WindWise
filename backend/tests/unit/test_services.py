"""Service-layer tests on a synthetic database: every number the API serves, without a web server."""
import tempfile
from datetime import date, time
from pathlib import Path

import pytest

from app.core.buffer import backtest_buffer, buffer_from_errors
from app.core.pipeline import daily_errors, evaluate_window, pooled_pairs
from app.core.stats import summarize
from app.repository.sqlite_repo import WindRepository
from app.scope import FIRST_DELIVERY, LAST_DELIVERY, delivery_days
from app.services import AnalyticsService
from synth_db import build_synthetic_db

_SVC = None


def svc() -> AnalyticsService:
    global _SVC
    if _SVC is None:
        db = build_synthetic_db(Path(tempfile.mkdtemp()) / "wind.sqlite")
        _SVC = AnalyticsService(WindRepository(db).load())
    return _SVC


CUT = time(9, 0)
ALL = (FIRST_DELIVERY, LAST_DELIVERY)


def test_meta():
    m = svc().meta()
    assert m["window"]["first_delivery"] == FIRST_DELIVERY and m["window"]["last_delivery"] == LAST_DELIVERY
    assert m["defaults"]["cutoff"] == "09:00" and m["defaults"]["confidence"] == 0.9
    assert m["run_times_utc"] == ["02:30", "04:30", "07:30", "09:30", "11:30", "15:30", "18:30", "22:30"]
    assert m["data"]["rows_actuals"] == 1680 and m["data"]["runs"] == 280
    assert len(m["assumptions"]) >= 5 and "forecast - actual" in m["sign_convention"]


def test_forecast_day_with_enough_history():
    out = svc().forecast(date(2026, 1, 20), CUT, 0.9)
    assert len(out["points"]) == 24 and out["counts"] == {"hours_total": 24, "missing_forecast": 0, "missing_actual": 0}
    assert out["decision_date"] == date(2026, 1, 19) and out["cutoff_utc"] == "2026-01-19T09:00:00Z"
    assert len(out["runs_used"]) == 1
    assert out["runs_used"][0]["publish_time"] == "2026-01-19T07:30:00Z"
    assert out["runs_used"][0]["age_hours_at_cutoff"] == 1.5
    assert out["buffer"]["status"] == "ok" and out["buffer"]["buffer_mw"] is not None
    p = out["points"][5]
    assert p["error_mw"] == pytest.approx(p["forecast_mw"] - p["actual_mw"], abs=0.11)
    assert p["firm_mw"] == pytest.approx(max(0.0, p["forecast_mw"] - out["buffer"]["buffer_mw"]), abs=0.11)
    assert p["corrected_mw"] is not None and p["baseline_mw"] is not None
    assert out["day_metrics"]["n"] == 24
    assert out["forecast_summary"]["peak_mw"] >= out["forecast_summary"]["mean_mw"] >= out["forecast_summary"]["min_mw"]


def test_forecast_early_day_has_no_buffer_and_says_why():
    out = svc().forecast(date(2026, 1, 3), CUT, 0.9)
    assert out["buffer"]["status"] == "insufficient_history" and out["buffer"]["buffer_mw"] is None
    assert all(p["firm_mw"] is None for p in out["points"])
    assert out["benchmark"]["status"] == "insufficient_history" and all(p["corrected_mw"] is None for p in out["points"])


def test_forecast_respects_the_cutoff():
    out = svc().forecast(date(2026, 1, 20), time(5, 0), 0.9)
    assert out["runs_used"][0]["publish_time"] == "2026-01-19T04:30:00Z"
    assert out["runs_used"][0]["age_hours_at_cutoff"] == 0.5
    early = svc().forecast(date(2026, 1, 20), time(3, 0), 0.9)
    assert early["runs_used"][0]["publish_time"] == "2026-01-19T02:30:00Z"


def test_summary_matches_the_core_directly():
    out = svc().summary(*ALL, CUT, 0.9)
    evs = evaluate_window(svc().ds.book, svc().ds.actuals, list(delivery_days()), CUT)
    f, a, _ = pooled_pairs(evs)
    m = summarize(f, a)
    assert out["metrics"]["n"] == 744 == out["counts"]["hours_scored"]
    assert out["metrics"]["bias"] == pytest.approx(m.bias, abs=0.06)
    assert out["metrics"]["rmse"] == pytest.approx(m.rmse, abs=0.06)
    errs = [e for ev in evs for e in ev.errors()]
    assert out["buffer_in_sample"]["buffer_mw"] == pytest.approx(buffer_from_errors(errs, 0.9), abs=0.06)
    bt = backtest_buffer(daily_errors(evs), 0.9, 7)
    assert out["backtest"]["hours_scored"] == bt.hours_scored and out["backtest"]["days_skipped"] == bt.days_skipped
    assert out["backtest"]["coverage"] == pytest.approx(bt.coverage, abs=1e-4)
    assert out["baseline"]["n"] == 744 and out["baseline"]["skill_mae"] is not None
    assert len(out["insights"]) >= 4


def test_summary_for_a_sub_range_still_uses_earlier_history():
    out = svc().summary(date(2026, 1, 20), date(2026, 1, 25), CUT, 0.9)
    assert out["metrics"]["n"] == 6 * 24 and out["range"]["n_days"] == 6
    assert out["backtest"]["days_scored"] == 6 and out["backtest"]["days_skipped"] == 0
    early = svc().summary(date(2026, 1, 2), date(2026, 1, 6), CUT, 0.9)
    assert early["backtest"]["days_scored"] == 0 and early["backtest"]["days_skipped"] == 5
    assert early["backtest"]["coverage"] is None


def test_intervals_are_ordered_and_contain_the_point():
    out = svc().intervals(*ALL, CUT, 0.9)
    for key in ("bias", "mae", "rmse", "buffer"):
        iv = out[key]
        assert iv["low"] <= iv["point"] <= iv["high"] and iv["n_days"] == 31 and iv["level"] == 0.9


def test_breakdowns():
    s = svc()
    assert [h["hour"] for h in s.by_hour(*ALL, CUT)["hours"]] == list(range(24))
    days = s.by_day(*ALL, CUT)["days"]
    assert len(days) == 31 and days[0]["delivery_date"] == FIRST_DELIVERY
    levels = s.by_forecast_level(*ALL, CUT)["levels"]
    assert [l["label"] for l in levels] == ["low", "medium", "high"]
    assert sum(l["metrics"]["n"] for l in levels) == 744
    dist = s.distribution(*ALL, CUT)
    assert dist["n"] == 744 and sum(b["count"] for b in dist["bins"]) == 744
    assert dist["p10"] <= dist["p50"] <= dist["p90"]


def test_horizon_views():
    s = svc()
    dec = s.horizon(*ALL, CUT, "decision")
    assert dec["view"] == "decision" and dec["bucket_hours"] == 6.0
    assert sum(b["metrics"]["n"] for b in dec["buckets"]) == 744 and not any(b["elapsed"] for b in dec["buckets"])
    full = s.horizon(*ALL, CUT, "full")
    elapsed = [b for b in full["buckets"] if b["elapsed"]]
    assert len(elapsed) == 1 and elapsed[0]["lower_h"] is None and elapsed[0]["metrics"]["n"] > 0
    assert full["buckets"][0]["elapsed"]


def test_runs_sensitivity():
    out = svc().runs(*ALL)
    assert [r["cutoff"] for r in out["results"]] == ["03:00", "05:00", "08:00", "09:00", "10:00", "12:00", "16:00"]
    default = next(r for r in out["results"] if r["cutoff"] == "09:00")
    assert default["mae_change_vs_default"] == 0.0 and default["runs_used"] == ["07:30"]
    assert next(r for r in out["results"] if r["cutoff"] == "08:00")["runs_used"] == ["07:30"]
    assert all(r["n_missing_forecast"] == 0 for r in out["results"])


def test_benchmarks():
    out = svc().benchmarks(*ALL, CUT)
    assert [b["method"] for b in out["bias_corrected"]] == ["ratio", "offset"]
    for b in out["bias_corrected"]:
        assert b["days_scored"] == 27 and b["official"]["n"] == b["corrected"]["n"] == 27 * 24
        assert b["rmse_improvement"] is not None
    assert "not the official forecast" in out["experimental_notice"]
    part = svc().benchmarks(date(2026, 1, 20), date(2026, 1, 25), CUT)
    assert part["bias_corrected"][0]["days_scored"] == 6 and part["bias_corrected"][0]["official"]["n"] == 144


def test_buffer_backtest_detail():
    out = svc().buffer_backtest(*ALL, CUT, 0.9)
    assert out["summary"]["days_scored"] == len(out["days"]) == 23
    assert out["summary"]["days_skipped"] == len(out["insufficient_history_days"]) == 8
    assert out["summary"]["hours_covered"] == sum(d["covered"] for d in out["days"])
    assert out["insufficient_history_days"][0] == FIRST_DELIVERY and out["days"][0]["history_days"] == 7
    assert all(d["mean_error_mw"] is not None for d in out["days"])