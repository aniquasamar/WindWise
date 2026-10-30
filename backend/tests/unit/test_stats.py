import math

import pytest

from app.core.stats import quantile, skill_score, summarize

# Worked example from the methodology: errors are +100, -50, +200, -150.
FORECAST = [3000, 2000, 4000, 1500]
ACTUAL = [2900, 2050, 3800, 1650]


def test_quantile_known_values():
    xs = [1, 2, 3, 4, 5]
    assert quantile(xs, 0.0) == 1
    assert quantile(xs, 0.5) == 3
    assert quantile(xs, 1.0) == 5
    assert quantile(xs, 0.9) == pytest.approx(4.6)


def test_quantile_interpolates_and_ignores_order():
    assert quantile([10, 0], 0.5) == 5
    assert quantile([4, 1, 3, 2], 0.25) == pytest.approx(1.75)


def test_quantile_rejects_bad_input():
    with pytest.raises(ValueError):
        quantile([], 0.5)
    with pytest.raises(ValueError):
        quantile([1, 2], 1.5)


def test_worked_example_headline_metrics():
    m = summarize(FORECAST, ACTUAL)
    assert m.n == 4
    assert m.bias == pytest.approx(25.0)
    assert m.mae == pytest.approx(125.0)
    assert m.rmse == pytest.approx(math.sqrt(18750))          # about 136.93
    assert m.std_error == pytest.approx(math.sqrt(18125))     # about 134.63
    assert m.over_share == pytest.approx(0.5)


def test_worked_example_relative_metrics():
    m = summarize(FORECAST, ACTUAL)
    assert m.mean_actual == pytest.approx(2600.0)
    assert m.nmae == pytest.approx(125 / 2600)
    assert m.nrmse == pytest.approx(math.sqrt(18750) / 2600)
    assert m.wmape == pytest.approx(500 / 10400)


def test_worked_example_percentiles():
    m = summarize(FORECAST, ACTUAL)
    assert m.p50_abs == pytest.approx(125.0)     # |e| sorted: 50, 100, 150, 200
    assert m.p90_abs == pytest.approx(185.0)
    assert m.p10_signed == pytest.approx(-120.0)  # e sorted: -150, -50, 100, 200
    assert m.p90_signed == pytest.approx(170.0)


def test_std_error_splits_rmse_into_offset_and_scatter():
    m = summarize(FORECAST, ACTUAL)
    assert m.rmse ** 2 == pytest.approx(m.bias ** 2 + m.std_error ** 2)


def test_empty_input_gives_n_zero_and_no_numbers():
    m = summarize([], [])
    assert m.n == 0 and m.bias is None and m.mae is None


def test_length_mismatch_raises():
    with pytest.raises(ValueError):
        summarize([1, 2], [1])


def test_percentage_metrics_are_none_when_actuals_are_zero():
    m = summarize([10, 20], [0, 0])
    assert m.nmae is None and m.wmape is None
    assert m.mae == pytest.approx(15.0)


def test_constant_over_forecast_has_zero_scatter():
    m = summarize([110, 210, 310], [100, 200, 300])
    assert m.bias == pytest.approx(10.0)
    assert m.std_error == pytest.approx(0.0, abs=1e-9)
    assert m.over_share == 1.0


def test_skill_score():
    assert skill_score(50, 100) == pytest.approx(0.5)
    assert skill_score(100, 100) == pytest.approx(0.0)
    assert skill_score(150, 100) == pytest.approx(-0.5)
    assert skill_score(None, 100) is None
    assert skill_score(50, 0) is None