from datetime import date, time

from app.core.timeutils import cutoff_utc, day_bounds_utc, decision_date_for, hourly_grid
from helpers import dt


def test_decision_date_is_day_before_delivery():
    assert decision_date_for(date(2026, 1, 15)) == date(2026, 1, 14)


def test_january_cutoff_equals_utc():
    assert cutoff_utc(date(2026, 1, 14), time(9, 0)) == dt(2026, 1, 14, 9)


def test_summer_cutoff_is_one_hour_earlier_in_utc():
    # Proves the conversion uses the real UK clock, even though project data is January only.
    assert cutoff_utc(date(2026, 7, 14), time(9, 0)) == dt(2026, 7, 14, 8)


def test_january_day_bounds_and_grid():
    start, end = day_bounds_utc(date(2026, 1, 15))
    assert start == dt(2026, 1, 15) and end == dt(2026, 1, 16)
    assert len(hourly_grid(start, end)) == 24


def test_spring_forward_day_has_23_hours():
    start, end = day_bounds_utc(date(2026, 3, 29))
    assert (end - start).total_seconds() == 23 * 3600
    assert len(hourly_grid(start, end)) == 23


def test_autumn_back_day_has_25_hours():
    start, end = day_bounds_utc(date(2026, 10, 25))
    assert len(hourly_grid(start, end)) == 25