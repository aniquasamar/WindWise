from datetime import date, time

import pytest

from app.core.selection import ForecastBook, ForecastRow, select_decision_forecast
from helpers import day_targets, dt, run_for_day

D = date(2026, 1, 15)  # delivery day; decision on 14 January, cutoff 09:00 UK (= 09:00 UTC)


def test_picks_latest_run_at_or_before_cutoff():
    rows = (
        run_for_day(dt(2026, 1, 14, 4, 30), D, 100)
        + run_for_day(dt(2026, 1, 14, 7, 30), D, 200)
        + run_for_day(dt(2026, 1, 14, 9, 30), D, 300)  # after the cutoff: must be ignored
    )
    result = select_decision_forecast(ForecastBook(rows), D)
    assert len(result.points) == 24
    assert {p.forecast_mw for p in result.points} == {200.0}
    assert result.runs_used == (dt(2026, 1, 14, 7, 30),)
    assert result.missing_targets == ()


def test_horizon_is_hours_between_publish_and_target():
    book = ForecastBook(run_for_day(dt(2026, 1, 14, 7, 30), D, 1))
    first = select_decision_forecast(book, D).points[0]
    assert first.target_time == dt(2026, 1, 15, 0)
    assert first.horizon_h == pytest.approx(16.5)
    last = select_decision_forecast(book, D).points[-1]
    assert last.horizon_h == pytest.approx(39.5)


def test_selection_is_per_target():
    early = [r for r in run_for_day(dt(2026, 1, 14, 4, 30), D, 100)]
    late = [r for r in run_for_day(dt(2026, 1, 14, 7, 30), D, 200) if r.target_time.hour >= 12]
    result = select_decision_forecast(ForecastBook(early + late), D)
    by_hour = {p.target_time.hour: p for p in result.points}
    assert by_hour[5].forecast_mw == 100 and by_hour[5].publish_time == dt(2026, 1, 14, 4, 30)
    assert by_hour[15].forecast_mw == 200 and by_hour[15].publish_time == dt(2026, 1, 14, 7, 30)


def test_other_days_targets_are_ignored():
    rows = run_for_day(dt(2026, 1, 14, 7, 30), D, 1) + run_for_day(dt(2026, 1, 14, 7, 30), date(2026, 1, 16), 2)
    result = select_decision_forecast(ForecastBook(rows), D)
    assert len(result.points) == 24
    assert all(p.target_time.date() == D for p in result.points)


def test_earlier_cutoff_selects_earlier_run():
    rows = run_for_day(dt(2026, 1, 14, 4, 30), D, 100) + run_for_day(dt(2026, 1, 14, 7, 30), D, 200)
    result = select_decision_forecast(ForecastBook(rows), D, cutoff_local=time(7, 0))
    assert {p.forecast_mw for p in result.points} == {100.0}


def test_summer_cutoff_uses_the_uk_clock():
    delivery = date(2026, 7, 15)
    rows = (
        run_for_day(dt(2026, 7, 14, 7, 30), delivery, 100)   # before 09:00 UK (= 08:00 UTC)
        + run_for_day(dt(2026, 7, 14, 8, 30), delivery, 200)  # 09:30 UK: after the cutoff
    )
    result = select_decision_forecast(ForecastBook(rows), delivery)
    assert {p.forecast_mw for p in result.points} == {100.0}
    assert len(result.points) == 24


def test_duplicate_publish_and_target_raises():
    t = day_targets(D)[0]
    rows = [ForecastRow(dt(2026, 1, 14, 7, 30), t, 1.0), ForecastRow(dt(2026, 1, 14, 7, 30), t, 2.0)]
    with pytest.raises(ValueError):
        ForecastBook(rows)


def test_empty_book_reports_everything_missing():
    result = select_decision_forecast(ForecastBook([]), D)
    assert result.points == () and len(result.missing_targets) == 24 and result.runs_used == ()