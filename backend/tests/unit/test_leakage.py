"""Leakage tests: they prove the central promise that nothing shown as "known at decision
time" uses information from after the decision. Each test changes only data that is NOT
allowed to matter and asserts the result is identical, then (where useful) changes data
that IS allowed to matter to show the test is sensitive.
"""
from datetime import date

from app.core.benchmark import correction_for_day, evaluate_benchmark
from app.core.buffer import expanding_buffer
from app.core.baseline import persistence_baseline
from app.core.pipeline import evaluate_delivery_day
from app.core.selection import ForecastBook, select_decision_forecast
from helpers import actuals_for_days, day_targets, dt, make_window, run_for_day

D = date(2026, 1, 15)
CUTOFF = dt(2026, 1, 14, 9)


def base_rows():
    return run_for_day(dt(2026, 1, 14, 4, 30), D, 100) + run_for_day(dt(2026, 1, 14, 7, 30), D, 200)


def test_runs_published_after_the_cutoff_never_change_the_selection():
    before = select_decision_forecast(ForecastBook(base_rows()), D)
    extra = (
        run_for_day(dt(2026, 1, 14, 9, 30), D, 1e9)
        + run_for_day(dt(2026, 1, 14, 15, 30), D, -1e9)
        + run_for_day(dt(2026, 1, 15, 2, 30), D, 5e8)   # even a run after delivery has begun
    )
    after = select_decision_forecast(ForecastBook(base_rows() + extra), D)
    assert after == before


def test_boundary_run_at_exactly_the_cutoff_is_included_one_second_later_is_not():
    on_time = run_for_day(dt(2026, 1, 14, 9, 0, 0), D, 300)
    late = run_for_day(dt(2026, 1, 14, 9, 0, 1), D, 400)
    result = select_decision_forecast(ForecastBook(base_rows() + on_time + late), D)
    assert {p.forecast_mw for p in result.points} == {300.0}
    assert result.runs_used == (dt(2026, 1, 14, 9, 0, 0),)


def test_a_target_with_only_a_later_run_is_missing_not_backfilled():
    early = [r for r in run_for_day(dt(2026, 1, 14, 7, 30), D, 200) if r.target_time.hour != 6]
    later = [r for r in run_for_day(dt(2026, 1, 14, 9, 30), D, 999) if r.target_time.hour == 6]
    result = select_decision_forecast(ForecastBook(early + later), D)
    assert [t.hour for t in result.missing_targets] == [6]
    assert all(p.target_time.hour != 6 for p in result.points)


def test_baseline_ignores_actuals_from_the_decision_day_and_later():
    actuals = actuals_for_days(date(2026, 1, 10), date(2026, 1, 16), lambda t: 100.0 * t.day)
    targets = day_targets(D)
    baseline = [persistence_baseline(actuals, t, CUTOFF) for t in targets]

    changed = dict(actuals)
    for t in list(changed):
        if t >= dt(2026, 1, 14):          # decision day, delivery day and after
            changed[t] = -12345.0
    assert [persistence_baseline(changed, t, CUTOFF) for t in targets] == baseline

    # Sensitivity: changing the 13th (the source day) must change it.
    moved = dict(actuals)
    for t in list(moved):
        if t.date() == date(2026, 1, 13):
            moved[t] = 5.0
    assert [persistence_baseline(moved, t, CUTOFF) for t in targets] != baseline


def test_buffer_ignores_errors_from_the_day_before_delivery_and_later():
    # Confidence 0.99 reads the very top of the history, so the sensitivity check below is real.
    daily = {date(2026, 1, n): [float(n)] * 24 for n in range(2, 20)}
    base = expanding_buffer(D, daily, 0.99, 7)
    assert base.buffer_mw == 13.0          # uses days 2..13 only (D-2 = the 13th)

    mutated = {d: list(v) for d, v in daily.items()}
    for n in (14, 15, 16, 17, 18, 19):     # D-1 (14th), D (15th) and later
        mutated[date(2026, 1, n)] = [9999.0] * 24
    assert expanding_buffer(D, mutated, 0.99, 7) == base

    # Sensitivity: the 13th (D-2) is allowed to matter, and does.
    mutated[date(2026, 1, 13)] = [9999.0] * 24
    assert expanding_buffer(D, mutated, 0.99, 7).buffer_mw == 9999.0


def test_forecast_selection_never_reads_actuals():
    book = ForecastBook(base_rows())
    quiet = actuals_for_days(date(2026, 1, 12), date(2026, 1, 16), 500.0)
    wild = actuals_for_days(date(2026, 1, 12), date(2026, 1, 16), 5e7)
    a = evaluate_delivery_day(book, quiet, D)
    b = evaluate_delivery_day(book, wild, D)
    assert [(p.target_time, p.forecast_mw, p.publish_time) for p in a.points] == [
        (p.target_time, p.forecast_mw, p.publish_time) for p in b.points
    ]


def test_full_pipeline_ignores_runs_published_after_the_cutoff():
    actuals = actuals_for_days(date(2026, 1, 12), date(2026, 1, 16), 150.0)
    clean = evaluate_delivery_day(ForecastBook(base_rows()), actuals, D)
    noisy = evaluate_delivery_day(
        ForecastBook(base_rows() + run_for_day(dt(2026, 1, 14, 11, 30), D, 1e7)), actuals, D
    )
    assert clean == noisy


def test_benchmark_correction_ignores_the_day_before_delivery_and_later():
    def pairs(bias):
        return ([1000.0 + bias] * 24, [1000.0] * 24)

    base_pairs = {date(2026, 1, n): pairs(100.0 + n) for n in range(2, 20)}
    base = correction_for_day(D, base_pairs, "ratio", window_days=7, min_days=3)

    mutated = dict(base_pairs)
    for n in (14, 15, 16, 17, 18, 19):          # D-1 (the 14th), D (the 15th) and later
        mutated[date(2026, 1, n)] = pairs(9999.0)
    assert correction_for_day(D, mutated, "ratio", 7, 3) == base

    mutated[date(2026, 1, 13)] = pairs(9999.0)  # D-2 is allowed to matter, and does
    assert correction_for_day(D, mutated, "ratio", 7, 3) != base


def test_benchmark_corrections_do_not_depend_on_a_days_own_or_later_actuals():
    book, actuals, days = make_window(date(2026, 1, 2), 10, lambda i, h: 1200, lambda i, h: 1000 + i)
    from app.core.pipeline import evaluate_window
    base = evaluate_benchmark(evaluate_window(book, actuals, days))

    changed = dict(actuals)
    for t in list(changed):
        if t.date() == days[5]:                  # alter day index 5 only
            changed[t] = 123.0
    other = evaluate_benchmark(evaluate_window(book, changed, days))

    before = dict(base.corrections)
    after = dict(other.corrections)
    for i in range(0, 7):                        # days 0..6 only use days up to index 4
        assert before[days[i]] == after[days[i]]
    assert before[days[7]] != after[days[7]]     # day 7 may use day 5, so it must differ