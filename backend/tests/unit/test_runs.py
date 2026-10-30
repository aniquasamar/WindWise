from datetime import date, time

import pytest

from app.core.runs import cutoff_sensitivity, percent_change
from app.core.selection import ForecastBook
from helpers import actuals_for_days, dt, run_for_day

DAYS = [date(2026, 1, 15), date(2026, 1, 16), date(2026, 1, 17)]


def book_and_actuals():
    rows = []
    for d in DAYS:
        prev = d.day - 1
        rows += run_for_day(dt(2026, 1, prev, 4, 30), d, 1100)
        rows += run_for_day(dt(2026, 1, prev, 7, 30), d, 1200)
    return ForecastBook(rows), actuals_for_days(date(2026, 1, 13), date(2026, 1, 17), 1000)


def test_each_cutoff_selects_the_run_published_before_it():
    book, actuals = book_and_actuals()
    res = cutoff_sensitivity(book, actuals, DAYS, [time(3, 0), time(5, 0), time(8, 0)])
    early, mid, late = res
    assert early.runs_used == () and early.metrics.n == 0 and early.n_missing_forecast == 72
    assert mid.runs_used == ("04:30",) and mid.metrics.bias == pytest.approx(100.0)
    assert late.runs_used == ("07:30",) and late.metrics.bias == pytest.approx(200.0)
    assert late.n_missing_forecast == 0


def test_percent_change():
    assert percent_change(200.0, 100.0) == pytest.approx(1.0)
    assert percent_change(50.0, 100.0) == pytest.approx(-0.5)
    assert percent_change(1.0, 0.0) is None and percent_change(None, 5.0) is None