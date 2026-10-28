"""Tests for scripts/ingest_elexon.py using synthetic, Elexon-shaped data.

No network and no real data needed: a complete fake window is generated, written
as raw files, and built into a temporary database.
"""
import importlib.util
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location("ingest_elexon", ROOT / "scripts" / "ingest_elexon.py")
ing = importlib.util.module_from_spec(_spec)
sys.modules["ingest_elexon"] = ing
_spec.loader.exec_module(ing)

UTC = timezone.utc
N_DAYS_ACTUALS = (ing.ACTUALS_LAST - ing.ACTUALS_FIRST).days + 1
N_DAYS_RUNS = (ing.FORECAST_PUBLISH_TO - ing.FORECAST_PUBLISH_FROM).days


def synth_actuals():
    rows = []
    t0 = ing.utc_midnight(ing.ACTUALS_FIRST)
    for i in range(N_DAYS_ACTUALS * 48):
        st = t0 + timedelta(minutes=30 * i)
        rows.append({
            "dataset": "FUELHH",
            "publishTime": ing.fmt_ts(st + timedelta(minutes=30)),
            "startTime": ing.fmt_ts(st),
            "settlementDate": st.date().isoformat(),
            "settlementPeriod": st.hour * 2 + st.minute // 30 + 1,
            "fuelType": "WIND",
            "generation": 10000 + i % 50,
        })
    return rows


def synth_forecasts(extra_run: bool = False):
    rows = []
    for d in range(N_DAYS_RUNS):
        day = ing.utc_midnight(ing.FORECAST_PUBLISH_FROM) + timedelta(days=d)
        times = sorted(ing.EXPECTED_RUN_TIMES)
        if extra_run and d == 3:
            times = times + ["12:25"]
        for hhmm in times:
            h, m = map(int, hhmm.split(":"))
            pub = day + timedelta(hours=h, minutes=m)
            first = (day - timedelta(days=1)).replace(hour=21)
            for k in range(ing.TARGETS_PER_RUN):
                rows.append({
                    "dataset": "WINDFOR",
                    "publishTime": ing.fmt_ts(pub),
                    "startTime": ing.fmt_ts(first + timedelta(hours=k)),
                    "generation": 9000 + k,
                })
    return rows


def write_raw(raw_dir: Path, actuals, forecasts):
    files = [
        ing.save_raw(raw_dir, "FUELHH", "all", {"synthetic": True}, actuals),
        ing.save_raw(raw_dir, "WINDFOR", "all", {"synthetic": True}, forecasts),
    ]
    ing.write_manifest(raw_dir, files, retrieved_at="2026-10-01T00:00:00Z")


def quiet(*_args, **_kw):
    pass


def test_valid_data_builds(tmp_path):
    write_raw(tmp_path / "raw", synth_actuals(), synth_forecasts())
    db = tmp_path / "wind.sqlite"
    meta = ing.build(tmp_path / "raw", db, out=quiet)

    con = sqlite3.connect(db)
    assert con.execute("SELECT COUNT(*) FROM actuals_half_hourly").fetchone()[0] == N_DAYS_ACTUALS * 48
    assert con.execute("SELECT COUNT(*) FROM forecasts").fetchone()[0] == (
        N_DAYS_RUNS * ing.RUNS_PER_DAY * ing.TARGETS_PER_RUN
    )
    assert con.execute("SELECT value FROM meta WHERE key='retrieved_at'").fetchone()[0] == "2026-10-01T00:00:00Z"
    assert meta["validation_issues_allowed"] == "no"
    con.close()


def test_build_is_deterministic(tmp_path):
    write_raw(tmp_path / "raw", synth_actuals(), synth_forecasts())
    m1 = ing.build(tmp_path / "raw", tmp_path / "a.sqlite", out=quiet)
    m2 = ing.build(tmp_path / "raw", tmp_path / "b.sqlite", out=quiet)
    assert m1["data_version"] == m2["data_version"]


def test_missing_half_hour_fails(tmp_path):
    actuals = synth_actuals()
    del actuals[100]
    write_raw(tmp_path / "raw", actuals, synth_forecasts())
    with pytest.raises(ing.ValidationFailed):
        ing.build(tmp_path / "raw", tmp_path / "wind.sqlite", out=quiet)
    assert not (tmp_path / "wind.sqlite").exists()


def test_null_actual_fails(tmp_path):
    actuals = synth_actuals()
    actuals[5]["generation"] = None
    write_raw(tmp_path / "raw", actuals, synth_forecasts())
    with pytest.raises(ing.ValidationFailed):
        ing.build(tmp_path / "raw", tmp_path / "wind.sqlite", out=quiet)


def test_short_run_fails(tmp_path):
    forecasts = synth_forecasts()
    del forecasts[10]
    write_raw(tmp_path / "raw", synth_actuals(), forecasts)
    with pytest.raises(ing.ValidationFailed):
        ing.build(tmp_path / "raw", tmp_path / "wind.sqlite", out=quiet)


def test_extra_run_in_a_day_fails_unless_allowed(tmp_path):
    write_raw(tmp_path / "raw", synth_actuals(), synth_forecasts(extra_run=True))
    with pytest.raises(ing.ValidationFailed):
        ing.build(tmp_path / "raw", tmp_path / "wind.sqlite", out=quiet)
    meta = ing.build(tmp_path / "raw", tmp_path / "wind.sqlite", allow_issues=True, out=quiet)
    assert meta["validation_issues_allowed"] == "yes"
    assert "12:25" in meta["unscheduled_runs"]


def test_late_run_is_recorded_not_fatal(tmp_path):
    """A run published at an unusual time (like 12:25 instead of 11:30) is a warning."""
    forecasts = synth_forecasts()
    day = ing.utc_midnight(ing.FORECAST_PUBLISH_FROM) + timedelta(days=5)
    old, new = ing.fmt_ts(day + timedelta(hours=11, minutes=30)), ing.fmt_ts(day + timedelta(hours=12, minutes=25))
    for r in forecasts:
        if r["publishTime"] == old:
            r["publishTime"] = new
    write_raw(tmp_path / "raw", synth_actuals(), forecasts)
    meta = ing.build(tmp_path / "raw", tmp_path / "wind.sqlite", out=quiet)
    assert meta["unscheduled_runs"].endswith("12:25:00Z")


def test_tampered_raw_file_is_detected(tmp_path):
    write_raw(tmp_path / "raw", synth_actuals(), synth_forecasts())
    f = tmp_path / "raw" / "FUELHH_all.json"
    f.write_bytes(f.read_bytes() + b" ")
    with pytest.raises(ing.ValidationFailed):
        ing.build(tmp_path / "raw", tmp_path / "wind.sqlite", out=quiet)


def test_identical_duplicate_rows_are_dropped(tmp_path):
    actuals = synth_actuals()
    actuals.append(dict(actuals[0]))
    write_raw(tmp_path / "raw", actuals, synth_forecasts())
    meta = ing.build(tmp_path / "raw", tmp_path / "wind.sqlite", out=quiet)
    assert meta["duplicates_dropped"] == "1"


def test_conflicting_duplicate_rows_fail(tmp_path):
    actuals = synth_actuals()
    clash = dict(actuals[0])
    clash["generation"] += 1
    actuals.append(clash)
    write_raw(tmp_path / "raw", actuals, synth_forecasts())
    with pytest.raises(ing.ValidationFailed):
        ing.build(tmp_path / "raw", tmp_path / "wind.sqlite", out=quiet)


def test_date_chunks_cover_range_without_overlap():
    from datetime import date
    chunks = list(ing.date_chunks(date(2026, 1, 1), date(2026, 1, 16), 7))
    assert chunks == [
        (date(2026, 1, 1), date(2026, 1, 7)),
        (date(2026, 1, 8), date(2026, 1, 14)),
        (date(2026, 1, 15), date(2026, 1, 16)),
    ]