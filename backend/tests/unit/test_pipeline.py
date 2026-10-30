from datetime import date

import pytest

from app.core.pipeline import daily_errors, evaluate_delivery_day, evaluate_window, pooled_pairs
from app.core.selection import ForecastBook
from app.core.stats import summarize
from helpers import actuals_for_days, dt, run_for_day

D = date(2026, 1, 15)


def make_book(mw=lambda i: 1000 + i):
    return ForecastBook(run_for_day(dt(2026, 1, 14, 7, 30), D, mw))


def make_actuals():
    # Actual = forecast - 100 for every hour of the 15th, plus data for the earlier days.
    actuals = actuals_for_days(date(2026, 1, 12), date(2026, 1, 14), 777.0)
    for i in range(24):
        for half in (0, 30):
            actuals[dt(2026, 1, 15, i, half)] = 1000.0 + i - 100.0
    return actuals


def test_sign_convention_over_forecast_is_positive():
    ev = evaluate_delivery_day(make_book(), make_actuals(), D)
    assert len(ev.points) == 24 and ev.n_missing_forecast == 0 and ev.n_missing_actual == 0
    assert all(p.error_mw == pytest.approx(100.0) for p in ev.points)
    m = summarize([p.forecast_mw for p in ev.scored()], [p.actual_mw for p in ev.scored()])
    assert m.bias == pytest.approx(100.0) and m.over_share == 1.0


def test_decision_metadata():
    ev = evaluate_delivery_day(make_book(), make_actuals(), D)
    assert ev.decision.decision_date == date(2026, 1, 14)
    assert ev.decision.cutoff_utc == dt(2026, 1, 14, 9)
    assert ev.points[0].horizon_h == pytest.approx(16.5)


def test_baseline_comes_from_two_days_before():
    ev = evaluate_delivery_day(make_book(), make_actuals(), D)
    assert all(p.baseline_mw == pytest.approx(777.0) for p in ev.points)


def test_missing_actual_hour_is_dropped_and_counted():
    actuals = make_actuals()
    del actuals[dt(2026, 1, 15, 10, 30)]
    ev = evaluate_delivery_day(make_book(), actuals, D)
    assert ev.n_missing_actual == 1 and len(ev.scored()) == 23
    assert ev.points[10].actual_mw is None and ev.points[10].error_mw is None


def test_missing_forecast_hours_are_counted():
    rows = [r for r in run_for_day(dt(2026, 1, 14, 7, 30), D, 1000) if r.target_time.hour != 3]
    ev = evaluate_delivery_day(ForecastBook(rows), make_actuals(), D)
    assert ev.n_missing_forecast == 1 and len(ev.points) == 23


def two_day_setup():
    d2 = date(2026, 1, 16)
    rows = run_for_day(dt(2026, 1, 14, 7, 30), D, 1000) + run_for_day(dt(2026, 1, 15, 7, 30), d2, 2000)
    actuals = actuals_for_days(date(2026, 1, 12), date(2026, 1, 16), 900.0)
    return ForecastBook(rows), actuals, d2


def test_evaluate_window_returns_one_evaluation_per_day_in_order():
    book, actuals, d2 = two_day_setup()
    evs = evaluate_window(book, actuals, [D, d2])
    assert [e.delivery_date for e in evs] == [D, d2]


def test_daily_errors_has_signed_errors_and_skips_unscorable_days():
    book, actuals, d2 = two_day_setup()
    del_actuals = {t: v for t, v in actuals.items() if t.date() != d2}   # no actuals on d2
    evs = evaluate_window(book, del_actuals, [D, d2])
    errs = daily_errors(evs)
    assert set(errs) == {D}
    assert errs[D] == [100.0] * 24


def test_pooled_pairs_and_baseline_filter():
    book, actuals, d2 = two_day_setup()
    evs = evaluate_window(book, actuals, [D, d2])
    f, a, b = pooled_pairs(evs)
    assert len(f) == len(a) == len(b) == 48
    # Remove the baseline source for the 16th (the 14th) so that day has no baseline.
    broken = {t: v for t, v in actuals.items() if t.date() != date(2026, 1, 14)}
    evs2 = evaluate_window(book, broken, [D, d2])
    f2, a2, b2 = pooled_pairs(evs2, require_baseline=True)
    assert len(f2) == 24 and all(x is not None for x in b2)