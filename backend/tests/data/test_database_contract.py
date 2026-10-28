"""Data contract tests for the real, committed database (data/wind.sqlite).

These guard the assumptions the whole app depends on. They are skipped (not failed)
if the database has not been built yet.
"""
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
DB = ROOT / "data" / "wind.sqlite"

pytestmark = pytest.mark.skipif(not DB.exists(), reason="data/wind.sqlite not built yet")

UTC = timezone.utc
FIRST_DELIVERY = date(2026, 1, 2)
LAST_DELIVERY = date(2026, 2, 1)


def ts(d: datetime) -> str:
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture(scope="module")
def con():
    # Same mode the deployed app will use: read-only and immutable.
    c = sqlite3.connect(f"{DB.as_uri()}?mode=ro&immutable=1", uri=True)
    yield c
    c.close()


def delivery_days():
    d = FIRST_DELIVERY
    while d <= LAST_DELIVERY:
        yield d
        d += timedelta(days=1)


def test_database_is_read_only(con):
    with pytest.raises(sqlite3.OperationalError):
        con.execute("INSERT INTO meta VALUES ('x', 'y')")


def test_meta_is_complete(con):
    meta = dict(con.execute("SELECT key, value FROM meta"))
    for key in ("schema_version", "retrieved_at", "source", "scope", "rows_actuals",
                "rows_forecasts", "runs", "data_version", "validation_issues_allowed"):
        assert key in meta, key
    assert meta["validation_issues_allowed"] == "no"


def test_meta_counts_match_tables(con):
    meta = dict(con.execute("SELECT key, value FROM meta"))
    assert int(meta["rows_actuals"]) == con.execute("SELECT COUNT(*) FROM actuals_half_hourly").fetchone()[0]
    assert int(meta["rows_forecasts"]) == con.execute("SELECT COUNT(*) FROM forecasts").fetchone()[0]


def test_actuals_have_no_gaps_for_delivery_window(con):
    start = datetime.combine(FIRST_DELIVERY, datetime.min.time(), tzinfo=UTC)
    n = ((LAST_DELIVERY - FIRST_DELIVERY).days + 1) * 48
    expected = {ts(start + timedelta(minutes=30 * i)) for i in range(n)}
    have = {r[0] for r in con.execute(
        "SELECT start_time FROM actuals_half_hourly WHERE start_time >= ? AND start_time <= ?",
        (min(expected), max(expected)),
    )}
    assert expected == have


def test_actuals_are_plausible(con):
    lo, hi, nulls = con.execute(
        "SELECT MIN(wind_mw), MAX(wind_mw), SUM(wind_mw IS NULL) FROM actuals_half_hourly"
    ).fetchone()
    assert nulls == 0
    assert lo >= 0
    assert hi < 40000  # far above anything seen; catches unit or scale mistakes


def test_every_run_has_73_hourly_targets(con):
    bad = con.execute(
        "SELECT publish_time, COUNT(*) c FROM forecasts GROUP BY publish_time HAVING c != 73"
    ).fetchall()
    assert bad == []


def test_eight_runs_per_day(con):
    bad = con.execute(
        "SELECT substr(publish_time, 1, 10) d, COUNT(DISTINCT publish_time) c "
        "FROM forecasts GROUP BY d HAVING c != 8"
    ).fetchall()
    assert bad == []


@pytest.mark.parametrize("delivery", list(delivery_days()), ids=str)
def test_decision_time_forecast_exists_for_all_24_hours(con, delivery):
    """At 09:00 on the decision date (UTC equals UK time in January) every hour of the
    delivery day must have at least one forecast published at or before the cutoff."""
    decision = delivery - timedelta(days=1)
    cutoff = ts(datetime.combine(decision, datetime.min.time(), tzinfo=UTC) + timedelta(hours=9))
    day_start = ts(datetime.combine(delivery, datetime.min.time(), tzinfo=UTC))
    day_end = ts(datetime.combine(delivery + timedelta(days=1), datetime.min.time(), tzinfo=UTC))
    (n,) = con.execute(
        "SELECT COUNT(DISTINCT start_time) FROM forecasts "
        "WHERE publish_time <= ? AND start_time >= ? AND start_time < ?",
        (cutoff, day_start, day_end),
    ).fetchone()
    assert n == 24


def test_no_forecast_row_is_published_after_its_target_ends_by_more_than_a_day(con):
    """Elapsed-target rows exist (negative horizons) but are bounded: at most 26 hours back."""
    (n,) = con.execute(
        "SELECT COUNT(*) FROM forecasts "
        "WHERE (julianday(publish_time) - julianday(start_time)) * 24 > 26"
    ).fetchone()
    assert n == 0