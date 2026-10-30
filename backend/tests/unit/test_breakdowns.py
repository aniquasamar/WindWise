from datetime import date

import pytest

from app.core.breakdowns import by_day, by_forecast_level, by_hour_of_day, error_histogram
from app.core.pipeline import evaluate_window
from helpers import make_window

FIRST = date(2026, 1, 10)


def evaluations(fc, act, n_days=3):
    book, actuals, days = make_window(FIRST, n_days, fc, act)
    return evaluate_window(book, actuals, days)


def test_by_hour_groups_all_24_hours_with_the_right_error():
    evs = evaluations(lambda i, h: 1000, lambda i, h: 1000 - 10 * h)   # error = +10 * hour
    groups = by_hour_of_day(evs)
    assert [g.hour for g in groups] == list(range(24))
    assert all(g.metrics.n == 3 for g in groups)
    assert groups[7].metrics.bias == pytest.approx(70.0)
    assert groups[0].metrics.bias == pytest.approx(0.0)


def test_by_day_reports_daily_bias_and_means():
    evs = evaluations(lambda i, h: 1000, lambda i, h: 1000 - 100 * (i + 1))   # +100, +200, +300
    days = by_day(evs)
    assert [d.metrics.bias for d in days] == [pytest.approx(100.0), pytest.approx(200.0), pytest.approx(300.0)]
    assert days[0].forecast_mean == pytest.approx(1000.0) and days[0].actual_mean == pytest.approx(900.0)
    assert days[0].delivery_date == FIRST


def test_by_forecast_level_splits_hours_into_terciles_by_the_forecast():
    # The actual runs OPPOSITE to the forecast, so grouping by actual instead would be caught.
    evs = evaluations(lambda i, h: 1000 + 100 * h, lambda i, h: 3300 - 100 * h, n_days=1)
    levels = by_forecast_level(evs)
    assert [l.label for l in levels] == ["low", "medium", "high"]
    assert [l.metrics.n for l in levels] == [8, 8, 8]
    assert levels[0].forecast_max < levels[1].forecast_min and levels[1].forecast_max < levels[2].forecast_min
    assert levels[0].metrics.mean_actual > levels[2].metrics.mean_actual     # low forecasts, high actuals


def test_by_forecast_level_is_empty_with_too_little_data():
    assert by_forecast_level([]) == []


def test_histogram_counts_and_edges():
    bins = error_histogram([-600, -100, 0, 450, 500, 1200], bin_width=500)
    assert [(b.lower, b.upper, b.count) for b in bins] == [
        (-1000, -500, 1), (-500, 0, 1), (0, 500, 2), (500, 1000, 1), (1000, 1500, 1),
    ]
    assert sum(b.count for b in bins) == 6


def test_histogram_edge_cases():
    assert error_histogram([]) == []
    with pytest.raises(ValueError):
        error_histogram([1.0], bin_width=0)