from datetime import date

import pytest

from app.core.buffer import (
    STATUS_INSUFFICIENT,
    STATUS_OK,
    backtest_buffer,
    buffer_from_errors,
    expanding_buffer,
    firm_wind,
    history_errors,
)


def day(n: int) -> date:
    return date(2026, 1, n)


def test_buffer_is_a_high_percentile_of_signed_error():
    errors = [-150.0, -50.0, 100.0, 200.0]
    assert buffer_from_errors(errors, 0.9) == pytest.approx(170.0)


def test_buffer_is_floored_at_zero():
    assert buffer_from_errors([-300.0, -200.0, -100.0], 0.9) == 0.0


def test_buffer_of_nothing_is_none():
    assert buffer_from_errors([], 0.9) is None


def test_higher_confidence_gives_a_larger_buffer():
    errors = [float(i) for i in range(100)]
    assert buffer_from_errors(errors, 0.95) > buffer_from_errors(errors, 0.80)


def test_firm_wind_subtracts_buffer_and_never_goes_negative():
    assert firm_wind(1000.0, 300.0) == 700.0
    assert firm_wind(200.0, 300.0) == 0.0


def test_history_only_includes_days_up_to_two_before_delivery():
    daily = {day(n): [float(n)] for n in range(2, 12)}
    errs, days = history_errors(day(10), daily)
    assert days == 7 and sorted(errs) == [float(n) for n in range(2, 9)]  # days 2..8


def test_insufficient_history_gives_no_buffer():
    daily = {day(n): [50.0] * 24 for n in range(2, 9)}
    res = expanding_buffer(day(9), daily, 0.9, min_days=7)  # usable: days up to the 7th = 6 days
    assert res.status == STATUS_INSUFFICIENT and res.buffer_mw is None and res.history_days == 6


def test_enough_history_gives_a_buffer():
    daily = {day(n): [50.0] * 24 for n in range(2, 9)}
    res = expanding_buffer(day(10), daily, 0.9, min_days=7)  # usable: days up to the 8th = 7 days
    assert res.status == STATUS_OK and res.buffer_mw == pytest.approx(50.0) and res.history_days == 7


def test_backtest_counts_coverage_hour_by_hour():
    daily = {day(n): [50.0] * 24 for n in range(2, 10)}   # steady +50 MW over-forecast
    daily[day(10)] = [80.0] * 24                           # a day worse than anything in history
    daily[day(11)] = [50.0] * 24
    result = backtest_buffer(daily, confidence=0.9, min_days=7)
    scored = {d.delivery_date: d for d in result.days}
    assert set(scored) == {day(10), day(11)}
    assert scored[day(10)].buffer_mw == pytest.approx(50.0) and scored[day(10)].covered == 0
    assert scored[day(11)].covered == 24
    assert result.days_skipped == 8                        # days 2..9 lack enough history
    assert result.hours_scored == 48 and result.hours_covered == 24
    assert result.coverage == pytest.approx(0.5)


def test_backtest_with_no_scorable_days_has_no_coverage():
    result = backtest_buffer({day(n): [10.0] for n in range(2, 5)}, 0.9, 7)
    assert result.coverage is None and result.days == ()