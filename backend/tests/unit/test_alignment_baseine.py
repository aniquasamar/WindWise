from datetime import date, datetime

import pytest

from app.core.alignment import hourly_actual
from app.core.baseline import actual_known_at, persistence_baseline
from helpers import actuals_for_days, day_targets, dt


def test_hourly_actual_is_mean_of_the_two_half_hours():
    actuals = {dt(2026, 1, 15, 10, 0): 100.0, dt(2026, 1, 15, 10, 30): 200.0}
    assert hourly_actual(actuals, dt(2026, 1, 15, 10)) == pytest.approx(150.0)


def test_hourly_actual_is_none_if_either_half_hour_is_missing():
    assert hourly_actual({dt(2026, 1, 15, 10, 0): 100.0}, dt(2026, 1, 15, 10)) is None
    assert hourly_actual({dt(2026, 1, 15, 10, 30): 100.0}, dt(2026, 1, 15, 10)) is None
    assert hourly_actual({}, dt(2026, 1, 15, 10)) is None


# Actuals equal 100 x day-of-month, so the source day of any baseline is easy to read off.
def by_day(t: datetime) -> float:
    return 100.0 * t.day


ACTUALS = actuals_for_days(date(2026, 1, 10), date(2026, 1, 16), by_day)
CUTOFF = dt(2026, 1, 14, 9)  # decision for delivery on the 15th


def test_baseline_is_the_same_hour_48_hours_earlier():
    assert persistence_baseline(ACTUALS, dt(2026, 1, 15, 10), CUTOFF) == pytest.approx(1300.0)


def test_baseline_never_uses_the_incomplete_decision_day():
    # Yesterday (the 14th) is incomplete at the cutoff. The baseline must come from the 13th.
    values = {persistence_baseline(ACTUALS, t, CUTOFF) for t in day_targets(date(2026, 1, 15))}
    assert values == {1300.0}


def test_all_24_baselines_exist_at_the_default_cutoff():
    assert all(persistence_baseline(ACTUALS, t, CUTOFF) is not None for t in day_targets(date(2026, 1, 15)))


def test_baseline_is_none_when_the_source_actual_is_missing():
    broken = dict(ACTUALS)
    del broken[dt(2026, 1, 13, 10, 30)]
    assert persistence_baseline(broken, dt(2026, 1, 15, 10), CUTOFF) is None


def test_availability_guard_blocks_actuals_not_yet_published():
    # The 10:00 hour ends at 11:00; with a 2.5 hour lag it is known from 13:30.
    hour = dt(2026, 1, 13, 10)
    assert not actual_known_at(hour, dt(2026, 1, 13, 13, 29))
    assert actual_known_at(hour, dt(2026, 1, 13, 13, 30))
    # So a (hypothetical) early cutoff yields no baseline rather than a leaked one.
    assert persistence_baseline(ACTUALS, dt(2026, 1, 15, 10), dt(2026, 1, 13, 12)) is None