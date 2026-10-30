#!/usr/bin/env python3
"""Run the analytics core on the real database and print every headline analysis.

Use it to sanity-check the core against the exploration results (DATA_NOTES.md section 6).
Run from the repository root:  python scripts/headline_check.py
Optional: python scripts/headline_check.py 08:00   (a different UK cutoff time)
"""
import sys
from collections import Counter
from datetime import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.benchmark import METHOD_OFFSET, METHOD_RATIO, evaluate_benchmark  # noqa: E402
from app.core.breakdowns import by_day, by_forecast_level, by_hour_of_day  # noqa: E402
from app.core.buffer import backtest_buffer, buffer_from_errors  # noqa: E402
from app.core.horizon import decision_time_horizon, full_horizon_curve  # noqa: E402
from app.core.insights import generate_insights  # noqa: E402
from app.core.pipeline import daily_errors, evaluate_window, pooled_pairs  # noqa: E402
from app.core.runs import cutoff_sensitivity, percent_change  # noqa: E402
from app.core.stats import skill_score, summarize  # noqa: E402
from app.core.uncertainty import bootstrap_interval, stat_bias, stat_buffer, stat_mae, stat_rmse  # noqa: E402
from app.repository.sqlite_repo import WindRepository  # noqa: E402
from app.scope import delivery_days  # noqa: E402


def mw(x):
    return "n/a" if x is None else f"{round(x):,}"


def pct(x, digits=1):
    return "n/a" if x is None else f"{100 * x:.{digits}f}%"


def section(title):
    print(f"\n=== {title} ===")


def main() -> None:
    cutoff = time(9, 0)
    if len(sys.argv) > 1:
        hh, mm = sys.argv[1].split(":")
        cutoff = time(int(hh), int(mm))

    ds = WindRepository(ROOT / "backend" / "data" / "wind.sqlite").load()
    days = list(delivery_days())
    evs = evaluate_window(ds.book, ds.actuals, days, cutoff)

    print(f"Database retrieved: {ds.meta.get('retrieved_at')}   data_version: {ds.meta.get('data_version', '')[:12]}")
    print(f"Window: {days[0]} to {days[-1]} ({len(days)} delivery days), cutoff {cutoff.strftime('%H:%M')} UK time")
    runs = Counter(r.strftime("%H:%M") for ev in evs for r in ev.decision.runs_used)
    print(f"Runs used (clock time UTC -> days): {dict(runs)}")
    print(f"Hours: scored {sum(len(e.scored()) for e in evs)}, "
          f"missing forecast {sum(e.n_missing_forecast for e in evs)}, "
          f"missing actual {sum(e.n_missing_actual for e in evs)}")

    # ------------------------------------------------------------------ headline
    f, a, _ = pooled_pairs(evs)
    m = summarize(f, a)
    section("Headline: decision-time forecast vs actual (error = forecast - actual, MW)")
    print(f"  n={m.n}  bias={mw(m.bias)}  MAE={mw(m.mae)}  RMSE={mw(m.rmse)}  std={mw(m.std_error)}")
    print(f"  mean actual={mw(m.mean_actual)}  nMAE={pct(m.nmae)}  nRMSE={pct(m.nrmse)}  WMAPE={pct(m.wmape)}")
    print(f"  P50/P90/P95 |error| = {mw(m.p50_abs)} / {mw(m.p90_abs)} / {mw(m.p95_abs)}")
    print(f"  signed P10 / P90 = {mw(m.p10_signed)} / {mw(m.p90_signed)}   over-forecast share = {pct(m.over_share)}")

    day_summaries = by_day(evs)
    over_days = sum(1 for d in day_summaries if d.metrics.bias is not None and d.metrics.bias > 0)
    worst = sorted(day_summaries, key=lambda d: -(d.metrics.bias or 0))[:3]
    print(f"  Days with positive mean error: {over_days} of {len(day_summaries)}")
    print("  Largest daily over-forecast: " + ", ".join(f"{d.delivery_date} {mw(d.metrics.bias)}" for d in worst))

    # ------------------------------------------------------------------ uncertainty
    daily = daily_errors(evs)
    section("Uncertainty: 90% day-block bootstrap intervals (resampling whole days, fixed seed)")
    for name, stat in (("bias", stat_bias), ("MAE", stat_mae), ("RMSE", stat_rmse), ("buffer @90%", stat_buffer(0.90))):
        iv = bootstrap_interval(daily, stat, level=0.90, n_boot=1000)
        print(f"  {name:12s} {mw(iv.point):>7s}   [{mw(iv.low)} to {mw(iv.high)}]   ({iv.n_days} days)")

    # ------------------------------------------------------------------ buffers
    errs = [e for ev in evs for e in ev.errors()]
    section("Buffer: in-sample (whole window) and out-of-sample backtest")
    for c in (0.80, 0.90, 0.95):
        print(f"  in-sample {int(c * 100)}%: {mw(buffer_from_errors(errs, c))} MW")
    for c in (0.90, 0.95):
        bt = backtest_buffer(daily, c, 7)
        print(f"  backtest {int(c * 100)}%: scored {len(bt.days)} days / {bt.hours_scored} hours, "
              f"skipped {bt.days_skipped}, coverage {pct(bt.coverage)}")

    bt90 = backtest_buffer(daily, 0.90, 7)
    by_date = {d.delivery_date: d for d in day_summaries}
    section("Per-day backtest at 90% (what the buffer was, and how it did)")
    print("  day         hist  buffer  covered   day mean error   day max error")
    for d in bt90.days:
        day_errs = daily[d.delivery_date]
        print(f"  {d.delivery_date}  {d.history_days:>3d}  {mw(d.buffer_mw):>6s}  {d.covered:>2d}/{d.hours:<2d}  "
              f"{mw(by_date[d.delivery_date].metrics.bias):>12s}   {mw(max(day_errs)):>10s}")

    # ------------------------------------------------------------------ breakdowns
    section("By hour of day (UK time): bias / MAE")
    hours = by_hour_of_day(evs)
    for i in range(0, len(hours), 2):
        left, right = hours[i], hours[i + 1] if i + 1 < len(hours) else None
        line = f"  {left.hour:02d}h {mw(left.metrics.bias):>6s} / {mw(left.metrics.mae):>6s}"
        if right:
            line += f"      {right.hour:02d}h {mw(right.metrics.bias):>6s} / {mw(right.metrics.mae):>6s}"
        print(line)

    section("By forecast level (terciles of the forecast)")
    for lv in by_forecast_level(evs):
        print(f"  {lv.label:7s} forecast {mw(lv.forecast_min):>6s}-{mw(lv.forecast_max):<6s}  n={lv.metrics.n:<4d}"
              f" bias={mw(lv.metrics.bias):>6s}  MAE={mw(lv.metrics.mae):>6s}  RMSE={mw(lv.metrics.rmse):>6s}"
              f"  nMAE={pct(lv.metrics.nmae)}")

    # ------------------------------------------------------------------ horizon
    section("Horizon, decision-time view (the forecast the buyer used), 6 h buckets")
    for b in decision_time_horizon(evs, 6.0):
        print(f"  {b.label:>18s}  n={b.metrics.n:<4d} bias={mw(b.metrics.bias):>6s}  MAE={mw(b.metrics.mae):>6s}  RMSE={mw(b.metrics.rmse):>6s}")
    section("Horizon, full curve (all runs, all window targets), 12 h buckets - descriptive only")
    for b in full_horizon_curve(ds.book, ds.actuals, days, 12.0):
        print(f"  {b.label:>28s}  n={b.metrics.n:<5d} bias={mw(b.metrics.bias):>6s}  MAE={mw(b.metrics.mae):>6s}  RMSE={mw(b.metrics.rmse):>6s}")

    # ------------------------------------------------------------------ run sensitivity
    section("Which run you act on (cutoff sensitivity)")
    sens = cutoff_sensitivity(ds.book, ds.actuals, days)
    ref = next((s for s in sens if s.cutoff == time(9, 0)), None)
    print("  cutoff  runs used          missing  bias    MAE    RMSE   MAE vs 09:00")
    for s in sens:
        chg = percent_change(s.metrics.mae, ref.metrics.mae if ref else None)
        print(f"  {s.cutoff.strftime('%H:%M')}   {','.join(s.runs_used) or '-':16s}  {s.n_missing_forecast:>5d}  "
              f"{mw(s.metrics.bias):>6s} {mw(s.metrics.mae):>6s} {mw(s.metrics.rmse):>6s}   {pct(chg) if s.metrics.n else 'n/a'}")

    # ------------------------------------------------------------------ baseline + benchmark
    f2, a2, b2 = pooled_pairs(evs, require_baseline=True)
    mf, mb = summarize(f2, a2), summarize(list(b2), a2)
    section(f"Baseline (same hour 48 h earlier), on the {mf.n} hours that have one")
    print(f"  forecast: bias={mw(mf.bias)} MAE={mw(mf.mae)} RMSE={mw(mf.rmse)}")
    print(f"  baseline: bias={mw(mb.bias)} MAE={mw(mb.mae)} RMSE={mw(mb.rmse)}")
    print(f"  skill: MAE {skill_score(mf.mae, mb.mae):.3f}   RMSE {skill_score(mf.rmse, mb.rmse):.3f}")

    section("EXPERIMENTAL benchmark: forecast corrected with past days only (7-day window, min 3 days)")
    for method in (METHOD_RATIO, METHOD_OFFSET):
        r = evaluate_benchmark(evs, method, 7, 3)
        print(f"  {method:6s} scored {r.days_scored} days / {r.raw.n} hours, skipped {r.days_skipped}")
        print(f"         official : bias={mw(r.raw.bias):>6s} MAE={mw(r.raw.mae):>6s} RMSE={mw(r.raw.rmse):>6s}")
        print(f"         corrected: bias={mw(r.corrected.bias):>6s} MAE={mw(r.corrected.mae):>6s} RMSE={mw(r.corrected.rmse):>6s}"
              f"   (RMSE improvement {pct(skill_score(r.corrected.rmse, r.raw.rmse))}, MAE {pct(skill_score(r.corrected.mae, r.raw.mae))})")

    # ------------------------------------------------------------------ insights
    section("Generated insight sentences")
    for line in generate_insights(m, day_summaries, buffer_from_errors(errs, 0.90), 0.90, bt90):
        print("  - " + line)


if __name__ == "__main__":
    main()