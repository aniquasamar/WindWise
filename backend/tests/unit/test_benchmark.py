from datetime import date

import pytest

from app.core.benchmark import (
    METHOD_OFFSET,
    METHOD_RATIO,
    STATUS_INSUFFICIENT,
    STATUS_OK,
    correction_for_day,
    evaluate_benchmark,
)
from app.core.pipeline import evaluate_window
from helpers import make_window


def d(n: int) -> date:
    return date(2026, 1, n)


def flat_pairs(days, f, a):
    return {d(n): ([float(f)] * 24, [float(a)] * 24) for n in days}


def test_ratio_correction_is_total_actual_over_total_forecast():
    c = correction_for_day(d(10), flat_pairs(range(1, 9), 1250, 1000), METHOD_RATIO)
    assert c.status == STATUS_OK and c.factor == pytest.approx(0.8)
    assert c.apply(1250.0) == pytest.approx(1000.0)


def test_offset_correction_subtracts_the_mean_error_and_floors_at_zero():
    c = correction_for_day(d(10), flat_pairs(range(1, 9), 1100, 1000), METHOD_OFFSET)
    assert c.factor == pytest.approx(100.0)
    assert c.apply(1100.0) == pytest.approx(1000.0)
    assert c.apply(40.0) == 0.0


def test_too_little_history_gives_no_correction():
    c = correction_for_day(d(5), flat_pairs([1, 2], 1250, 1000))     # usable days <= 3: only 2
    assert c.status == STATUS_INSUFFICIENT and c.factor is None and c.history_days == 2
    assert c.apply(1000.0) is None


def test_only_the_most_recent_window_days_are_used():
    pairs = {d(n): ([2000.0] * 24, [1000.0] * 24) for n in range(1, 5)}         # old: badly biased
    pairs.update({d(n): ([1000.0] * 24, [1000.0] * 24) for n in range(5, 13)})  # recent: unbiased
    recent = correction_for_day(d(14), pairs, METHOD_RATIO, window_days=7)
    assert recent.factor == pytest.approx(1.0) and recent.history_days == 7
    everything = correction_for_day(d(14), pairs, METHOD_RATIO, window_days=100)
    assert everything.factor < 1.0


def test_unknown_method_raises():
    with pytest.raises(ValueError):
        correction_for_day(d(10), flat_pairs(range(1, 9), 1, 1), "magic")


def test_evaluate_benchmark_removes_a_constant_over_forecast():
    book, actuals, days = make_window(d(2), 8, lambda i, h: 1250, lambda i, h: 1000)
    evs = evaluate_window(book, actuals, days)
    for method in (METHOD_RATIO, METHOD_OFFSET):
        res = evaluate_benchmark(evs, method, window_days=7, min_days=3)
        assert res.days_scored == 4 and res.days_skipped == 4      # days 2..5 lack 3 days of history
        assert res.raw.n == res.corrected.n == 4 * 24             # compared on the same hours
        assert res.raw.bias == pytest.approx(250.0)
        assert res.corrected.bias == pytest.approx(0.0, abs=1e-6)
        assert res.corrected.rmse < res.raw.rmse


def test_score_dates_limits_scoring_but_not_learning():
    book, actuals, days = make_window(d(2), 8, lambda i, h: 1250, lambda i, h: 1000)
    evs = evaluate_window(book, actuals, days)
    full = evaluate_benchmark(evs, METHOD_RATIO, 7, 3)
    late = {d(7), d(8), d(9)}
    part = evaluate_benchmark(evs, METHOD_RATIO, 7, 3, score_dates=late)
    assert part.days_scored == 3 and part.raw.n == 3 * 24
    assert part.corrected.bias == pytest.approx(0.0, abs=1e-6)     # history came from the earlier days
    assert full.days_scored == 4