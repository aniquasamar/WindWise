import assert from "node:assert/strict";
import { test } from "node:test";
import type { DayOut, MetricsOut, PointOut } from "../src/api/types";
import { clampDate, cutoffOptions, dayResult, isIsoDate, largestMissDate, peakPoint, shiftDate } from "../src/lib/derive";

function point(forecast: number, actual: number | null, firm: number | null): PointOut {
  return {
    time: "2026-01-15T00:00:00Z", forecast_mw: forecast, actual_mw: actual,
    error_mw: actual === null ? null : forecast - actual, horizon_h: 16.5, baseline_mw: null, firm_mw: firm, corrected_mw: null,
  };
}
const metrics = (bias: number | null): MetricsOut => ({
  n: 24, bias, mae: null, rmse: null, std_error: null, mean_actual: null, nmae: null, nrmse: null, wmape: null,
  p50_abs: null, p90_abs: null, p95_abs: null, p10_signed: null, p90_signed: null, over_share: null,
});
const day = (d: string, bias: number | null): DayOut => ({ delivery_date: d, forecast_mean: null, actual_mean: null, metrics: metrics(bias) });

test("dayResult counts hours where actual wind met the firm level", () => {
  const r = dayResult([point(1000, 900, 700), point(1000, 600, 700), point(1000, 1100, 700), point(1000, null, 700)]);
  assert.equal(r.scoredHours, 3);
  assert.equal(r.meanError, (100 + 400 - 100) / 3);
  assert.equal(r.firmHours, 3);
  assert.equal(r.firmHeldHours, 2);
});

test("dayResult without a buffer or actuals", () => {
  assert.equal(dayResult([point(1000, 900, null)]).firmHeldHours, null);
  const none = dayResult([point(1000, null, 700)]);
  assert.equal(none.scoredHours, 0);
  assert.equal(none.meanError, null);
});

test("peakPoint", () => {
  assert.equal(peakPoint([point(1, 0, null), point(9, 0, null), point(5, 0, null)])?.forecast_mw, 9);
  assert.equal(peakPoint([]), null);
});

test("largestMissDate considers size, not direction", () => {
  assert.equal(largestMissDate([day("2026-01-05", 100), day("2026-01-06", -900), day("2026-01-07", 500)]), "2026-01-06");
  assert.equal(largestMissDate([day("2026-01-05", null)]), null);
  assert.equal(largestMissDate([]), null);
});

test("date helpers", () => {
  assert.ok(isIsoDate("2026-01-28"));
  assert.ok(!isIsoDate("28/01/2026") && !isIsoDate(null) && !isIsoDate("2026-13-45") && !isIsoDate("<script>"));
  assert.equal(clampDate("2025-12-01", "2026-01-02", "2026-02-01"), "2026-01-02");
  assert.equal(clampDate("2027-01-01", "2026-01-02", "2026-02-01"), "2026-02-01");
  assert.equal(clampDate("2026-01-10", "2026-01-02", "2026-02-01"), "2026-01-10");
  assert.equal(shiftDate("2026-01-31", 1), "2026-02-01");
  assert.equal(shiftDate("2026-01-01", -1), "2025-12-31");
});

test("cutoff options step in 15 minutes from min to max inclusive", () => {
  const o = cutoffOptions("03:00", "16:00", 15);
  assert.equal(o[0], "03:00");
  assert.equal(o[o.length - 1], "16:00");
  assert.equal(o.length, 53);
  assert.ok(o.includes("09:00") && o.includes("12:45"));
});