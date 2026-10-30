from datetime import date, timedelta

import pytest

from app.core.uncertainty import bootstrap_interval, stat_bias, stat_buffer, stat_mae, stat_rmse


def days(values_by_day):
    start = date(2026, 1, 2)
    return {start + timedelta(days=i): list(v) for i, v in enumerate(values_by_day)}


def test_statistic_helpers():
    errs = [100.0, -50.0, 200.0, -150.0]
    assert stat_bias(errs) == pytest.approx(25.0)
    assert stat_mae(errs) == pytest.approx(125.0)
    assert stat_rmse(errs) ** 2 == pytest.approx(18750.0)
    assert stat_buffer(0.9)(errs) == pytest.approx(170.0)
    assert stat_bias([]) is None and stat_buffer(0.9)([]) is None


def test_interval_is_deterministic_for_a_fixed_seed():
    data = days([[10, 20, 30], [40, 50, 60], [5, 5, 5], [100, 90, 80], [0, 1, 2]])
    a = bootstrap_interval(data, stat_bias, n_boot=300, seed=1)
    b = bootstrap_interval(data, stat_bias, n_boot=300, seed=1)
    assert a == b


def test_constant_errors_give_a_degenerate_interval():
    data = days([[50.0] * 24 for _ in range(10)])
    iv = bootstrap_interval(data, stat_bias, n_boot=200)
    assert iv.point == iv.low == iv.high == pytest.approx(50.0)


def test_interval_contains_the_point_estimate_and_is_ordered():
    data = days([[i * 3.0 + j for j in range(24)] for i in range(20)])
    iv = bootstrap_interval(data, stat_mae, level=0.9, n_boot=500)
    assert iv.low <= iv.point <= iv.high and iv.n_days == 20 and iv.level == 0.9


def test_more_variable_days_give_a_wider_interval():
    calm = days([[100 + (i % 3)] * 24 for i in range(20)])
    wild = days([[100 + 80 * ((i * 7) % 5 - 2)] * 24 for i in range(20)])
    w = lambda iv: iv.high - iv.low
    assert w(bootstrap_interval(wild, stat_bias, n_boot=400)) > w(bootstrap_interval(calm, stat_bias, n_boot=400))


def test_fewer_than_two_days_has_no_interval():
    iv = bootstrap_interval(days([[1.0, 2.0]]), stat_bias)
    assert iv.point == pytest.approx(1.5) and iv.low is None and iv.high is None