import assert from "node:assert/strict";
import { test } from "node:test";
import type { BenchmarksOut, BufferBacktestOut, DayOut, DistributionOut, HorizonOut, HourOut, IntervalOut, LevelOut, MetricsOut, RunsOut } from "../src/api/types";
import { backtestCaption, benchmarkCaption, dayCaption, distributionCaption, horizonCaption, hourCaption, intervalText, levelCaption, runsCaption } from "../src/lib/captions";

const m = (over: Partial<MetricsOut> = {}): MetricsOut => ({
  n: 100, bias: null, mae: null, rmse: null, std_error: null, mean_actual: null, nmae: null, nrmse: null, wmape: null,
  p50_abs: null, p90_abs: null, p95_abs: null, p10_signed: null, p90_signed: null, over_share: null, ...over,
});
const range = { first: "2026-01-02", last: "2026-02-01", n_days: 31 };

test("day caption counts days and names the largest miss", () => {
  const days: DayOut[] = [
    { delivery_date: "2026-01-05", forecast_mean: 1, actual_mean: 1, metrics: m({ bias: 100 }) },
    { delivery_date: "2026-01-28", forecast_mean: 1, actual_mean: 1, metrics: m({ bias: 5375 }) },
    { delivery_date: "2026-01-19", forecast_mean: 1, actual_mean: 1, metrics: m({ bias: -684 }) },
  ];
  assert.equal(dayCaption(days), "The forecast was too high on average on 2 of 3 days. The largest miss was 28 Jan, at +5,375 MW.");
  assert.equal(dayCaption([]), null);
});

test("hour caption names the extremes", () => {
  const hours: HourOut[] = [5, 15, 9].map((hour, i) => ({ hour, metrics: m({ bias: [2358, 1247, 1854][i] }) }));
  const text = hourCaption(hours) ?? "";
  assert.ok(text.includes("05:00") && text.includes("+2,358 MW") && text.includes("15:00") && text.includes("+1,247 MW"));
  assert.equal(hourCaption([hours[0]]), null);
});

test("level caption contrasts windy and calm days", () => {
  const lv = (label: string, lo: number, hi: number, bias: number, p90: number): LevelOut => ({
    label, forecast_min: lo, forecast_max: hi, metrics: m({ bias, p90_signed: p90 }),
  });
  const text = levelCaption([lv("low", 3161, 10099, 746, 2500), lv("medium", 10118, 16655, 1568, 3500), lv("high", 16658, 21064, 2929, 4900)]) ?? "";
  assert.ok(text.includes("above 16,658 MW") && text.includes("2,929 MW") && text.includes("4,900 MW") && text.includes("below 10,099 MW") && text.includes("746 MW"));
  assert.equal(levelCaption([]), null);
});

test("distribution caption handles both signs of the lower tail", () => {
  const d: DistributionOut = { range, cutoff: "09:00", bin_width_mw: 500, n: 744, bins: [], p10: -549, p50: 1671, p90: 4098 };
  const text = distributionCaption(d) ?? "";
  assert.ok(text.includes("+1,671 MW") && text.includes("4,098 MW") && text.includes("under-forecast by more than 549 MW"));
  assert.ok((distributionCaption({ ...d, p10: 200 }) ?? "").includes("at least +200 MW"));
  assert.equal(distributionCaption({ ...d, p50: null }), null);
});

test("backtest caption lists the worst days first", () => {
  const day = (date: string, covered: number) => ({ delivery_date: date, buffer_mw: 3500, history_days: 10, hours: 24, covered, mean_error_mw: 1000 });
  const b: BufferBacktestOut = {
    range, cutoff: "09:00", confidence: 0.9, days: [day("2026-01-10", 24), day("2026-01-12", 6), day("2026-01-11", 0)],
    summary: { confidence: 0.9, min_history_days: 7, days_scored: 3, days_skipped: 0, hours_scored: 72, hours_covered: 30, coverage: 0.4167 },
    insufficient_history_days: [],
  };
  assert.equal(backtestCaption(b), "The buffer held for every hour on 1 of 3 tested days. Shortfalls: 11 Jan (0 of 24 hours), 12 Jan (6 of 24 hours).");
  assert.equal(backtestCaption({ ...b, days: [] }), null);
});

test("horizon caption compares the shortest and longest horizons and mentions elapsed hours", () => {
  const bucket = (label: string, mae: number, n: number, elapsed = false) => ({ label, lower_h: elapsed ? null : 0, upper_h: 12, elapsed, metrics: m({ mae, n }) });
  const h: HorizonOut = {
    range, cutoff: "09:00", view: "full", bucket_hours: 12, note: "",
    buckets: [bucket("already elapsed (0 h or less)", 1800, 3697, true), bucket("0 to 12 h", 1697, 2976), bucket("60 to 72 h", 2370, 434)],
  };
  const text = horizonCaption(h) ?? "";
  assert.ok(text.includes("1,697 MW (0 to 12 h)") && text.includes("2,370 MW (60 to 72 h)") && text.includes("40% higher"));
  assert.ok(text.includes("already happened") && text.includes("1,800 MW"));
  assert.equal(horizonCaption({ ...h, view: "decision" }), null);
});

test("runs caption separates the cutoffs that matter from the ones that arrive too late", () => {
  const r = (cutoff: string, change: number) => ({ cutoff, runs_used: [], n_missing_forecast: 0, metrics: m({ mae: 2000 }), mae_change_vs_default: change, rmse_change_vs_default: change });
  const runs: RunsOut = {
    range, default_cutoff: "09:00", note: "",
    results: [r("03:00", 0.017), r("05:00", -0.011), r("09:00", 0), r("10:00", -0.013), r("16:00", -0.081)],
  };
  const text = runsCaption(runs) ?? "";
  assert.ok(text.includes("Cutoffs up to 09:00") && text.includes("at most 1.7%"));
  assert.ok(text.includes("up to 8.1% better") && text.includes("after the hourly day-ahead auctions close"));
});

test("benchmark caption reports both methods and calls the result experimental", () => {
  const entry = (method: string, mae: number) => ({
    method, window_days: 7, min_days: 3, days_scored: 27, days_skipped: 4, official: m(), corrected: m(), rmse_improvement: 0.2, mae_improvement: mae,
  });
  const b = { range, cutoff: "09:00", baseline: {} as never, experimental_notice: "", bias_corrected: [entry("ratio", 0.328), entry("offset", 0.235)] } as BenchmarksOut;
  const text = benchmarkCaption(b) ?? "";
  assert.ok(text.includes("previous 7 days") && text.includes("33%") && text.includes("24%") && text.includes("27 days") && text.includes("experiment"));
  assert.equal(benchmarkCaption({ ...b, bias_corrected: [] }), null);
});

test("interval text", () => {
  const iv: IntervalOut = { point: 1748, low: 1313, high: 2195, level: 0.9, n_days: 31, n_boot: 1000 };
  assert.equal(intervalText(iv), "90% range: 1,313 to 2,195 MW");
  assert.equal(intervalText({ ...iv, low: -120, high: 400 }, true), "90% range: \u2212120 to +400 MW");
  assert.equal(intervalText({ ...iv, low: null }), null);
  assert.equal(intervalText(undefined), null);
});