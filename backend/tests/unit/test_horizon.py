from datetime import date

import pytest

from app.core.horizon import ELAPSED, bucket_index, bucket_label, decision_time_horizon, full_horizon_curve
from app.core.pipeline import evaluate_window
from app.core.selection import ForecastBook
from helpers import actuals_for_days, dt, make_window, run_for_day


def test_bucket_index_uses_right_closed_buckets_and_a_separate_elapsed_bucket():
    assert bucket_index(0, 12) == ELAPSED and bucket_index(-5.5, 12) == ELAPSED
    assert bucket_index(0.5, 12) == 0 and bucket_index(12, 12) == 0
    assert bucket_index(12.5, 12) == 1 and bucket_index(24, 12) == 1 and bucket_index(24.5, 12) == 2


def test_bucket_labels():
    assert bucket_label(ELAPSED, 12) == "already elapsed (0 h or less)"
    assert bucket_label(2, 6) == "12 to 18 h"


def test_decision_time_horizon_covers_16_to_40_hours():
    book, actuals, days = make_window(date(2026, 1, 10), 3, lambda i, h: 1000, lambda i, h: 900)
    buckets = decision_time_horizon(evaluate_window(book, actuals, days), width=6)
    assert [b.index for b in buckets] == [2, 3, 4, 5, 6]
    assert [b.metrics.n for b in buckets] == [6, 18, 18, 18, 12]      # 2,6,6,6,4 hours per day x 3 days
    assert all(b.metrics.bias == pytest.approx(100.0) for b in buckets)
    assert not any(b.elapsed for b in buckets)


def test_full_curve_separates_elapsed_targets_from_forecasts():
    d = date(2026, 1, 15)
    far = run_for_day(dt(2026, 1, 13, 7, 30), d, 1000)       # horizons 40.5 .. 63.5
    after = run_for_day(dt(2026, 1, 15, 6, 30), d, 2000)     # horizons -6.5 .. 16.5
    actuals = actuals_for_days(d, d, 1500)
    buckets = {b.index: b for b in full_horizon_curve(ForecastBook(far + after), actuals, [d], width=12)}
    assert buckets[ELAPSED].metrics.n == 7                    # hours 0..6 were already over
    assert buckets[ELAPSED].metrics.bias == pytest.approx(500.0)
    assert buckets[ELAPSED].elapsed
    assert buckets[0].metrics.n == 12 and buckets[1].metrics.n == 5
    assert all(buckets[i].metrics.bias == pytest.approx(-500.0) for i in (3, 4, 5))
    assert sum(b.metrics.n for b in buckets.values()) == 48


def test_full_curve_skips_hours_without_an_actual():
    d = date(2026, 1, 15)
    actuals = actuals_for_days(d, d, 1500)
    del actuals[dt(2026, 1, 15, 3, 30)]
    rows = run_for_day(dt(2026, 1, 14, 7, 30), d, 1000)
    buckets = full_horizon_curve(ForecastBook(rows), actuals, [d], width=12)
    assert sum(b.metrics.n for b in buckets) == 23