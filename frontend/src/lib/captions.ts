// One-sentence takeaways shown under each chart. They are built from the same numbers as the
// chart, so the words can never disagree with the picture. Pure functions, unit-tested.
import type { BenchmarksOut, BufferBacktestOut, DayOut, DistributionOut, HorizonOut, HourOut, IntervalOut, LevelOut, RunsOut } from "../api/types";
import { fmtDateShort, fmtMw, fmtNumber, fmtPct } from "./format";

const hourLabel = (h: number) => `${String(h).padStart(2, "0")}:00`;

export function dayCaption(days: DayOut[]): string | null {
  const scored = days.filter((d) => d.metrics.bias !== null);
  if (scored.length === 0) return null;
  const over = scored.filter((d) => (d.metrics.bias as number) > 0).length;
  const worst = scored.reduce((a, b) => (Math.abs(b.metrics.bias as number) > Math.abs(a.metrics.bias as number) ? b : a));
  return `The forecast was too high on average on ${over} of ${scored.length} days. The largest miss was ${fmtDateShort(worst.delivery_date)}, at ${fmtMw(worst.metrics.bias, true)}.`;
}

export function hourCaption(hours: HourOut[]): string | null {
  const scored = hours.filter((h) => h.metrics.bias !== null);
  if (scored.length < 2) return null;
  const hi = scored.reduce((a, b) => ((b.metrics.bias as number) > (a.metrics.bias as number) ? b : a));
  const lo = scored.reduce((a, b) => ((b.metrics.bias as number) < (a.metrics.bias as number) ? b : a));
  return `The forecast is furthest too high at ${hourLabel(hi.hour)} (${fmtMw(hi.metrics.bias, true)}) and closest at ${hourLabel(lo.hour)} (${fmtMw(lo.metrics.bias, true)}). The dotted line is the hourly buffer for 9 hours in 10.`;
}

export function levelCaption(levels: LevelOut[]): string | null {
  if (levels.length < 3) return null;
  const low = levels[0];
  const high = levels[levels.length - 1];
  if (low.metrics.bias === null || high.metrics.bias === null || high.metrics.p90_signed === null) return null;
  return `When the forecast is high (above ${fmtMw(high.forecast_min)}), actual wind fell short by ${fmtMw(high.metrics.bias)} on average, and by more than ${fmtMw(high.metrics.p90_signed)} in one hour in ten. When it is low (below ${fmtMw(low.forecast_max)}), the average shortfall is ${fmtMw(low.metrics.bias)}. One flat buffer is too big for calm days and too small for windy ones.`;
}

export function distributionCaption(d: DistributionOut): string | null {
  if (d.p10 === null || d.p50 === null || d.p90 === null) return null;
  const lower = d.p10 < 0 ? `one in ten is under-forecast by more than ${fmtMw(-d.p10)}` : `nine in ten hours are at least ${fmtMw(d.p10, true)}`;
  return `The middle hour is ${fmtMw(d.p50, true)}; one hour in ten is over-forecast by more than ${fmtMw(d.p90)}, and ${lower}. Bars are ${d.bin_width_mw} MW wide, labelled where each starts.`;
}

export function backtestCaption(b: BufferBacktestOut): string | null {
  const days = b.days;
  if (days.length === 0) return null;
  const full = days.filter((d) => d.covered === d.hours).length;
  const missed = days.filter((d) => d.covered < d.hours).sort((a, c) => a.covered / a.hours - c.covered / c.hours);
  let text = `The buffer held for every hour on ${full} of ${days.length} tested days.`;
  if (missed.length) {
    text += ` Shortfalls: ${missed.slice(0, 5).map((d) => `${fmtDateShort(d.delivery_date)} (${d.covered} of ${d.hours} hours)`).join(", ")}.`;
  }
  return text;
}

export function horizonCaption(h: HorizonOut): string | null {
  if (h.view !== "full") return null;
  const ahead = h.buckets.filter((b) => !b.elapsed && b.metrics.mae !== null && b.metrics.n >= 100);
  const elapsed = h.buckets.find((b) => b.elapsed && b.metrics.mae !== null);
  if (ahead.length < 2) return null;
  const first = ahead[0];
  const last = ahead[ahead.length - 1];
  let text = `The typical miss grows from ${fmtMw(first.metrics.mae)} (${first.label}) to ${fmtMw(last.metrics.mae)} (${last.label}), ${fmtPct((last.metrics.mae as number) / (first.metrics.mae as number) - 1)} higher.`;
  if (elapsed) {
    text += ` Hours that had already happened when the run was published still show a miss of ${fmtMw(elapsed.metrics.mae)}, which points to a persistent gap between the two series, not to forecasting skill alone.`;
  }
  return text;
}

export function runsCaption(r: RunsOut): string | null {
  const results = r.results.filter((x) => x.metrics.mae !== null && x.mae_change_vs_default !== null);
  if (results.length < 2) return null;
  const early = results.filter((x) => x.cutoff <= "09:00");
  const late = results.filter((x) => x.cutoff > "09:00");
  const maxEarly = Math.max(0, ...early.map((x) => Math.abs(x.mae_change_vs_default as number)));
  const bestLate = Math.min(0, ...late.map((x) => x.mae_change_vs_default as number));
  let text = `Cutoffs up to ${early.length ? early[early.length - 1].cutoff : r.default_cutoff} change the typical miss by at most ${fmtPct(maxEarly, 1)}.`;
  if (bestLate < -0.005) {
    text += ` Later runs are up to ${fmtPct(-bestLate, 1)} better, but they are published after the hourly day-ahead auctions close (typically 09:20 to 09:50 UK time; confirm the current timetable).`;
  }
  return text;
}

export function benchmarkCaption(b: BenchmarksOut): string | null {
  const ratio = b.bias_corrected.find((x) => x.method === "ratio");
  const offset = b.bias_corrected.find((x) => x.method === "offset");
  if (!ratio || ratio.mae_improvement === null || ratio.days_scored === 0) return null;
  let text = `Correcting the forecast using only the previous ${ratio.window_days} days would have cut the typical miss by ${fmtPct(ratio.mae_improvement)} (ratio method) over ${ratio.days_scored} days`;
  if (offset && offset.mae_improvement !== null) text += `, and by ${fmtPct(offset.mae_improvement)} with the simpler offset method`;
  return text + ". This is an experiment, not the official forecast.";
}

/** "90% range: 1,313 to 2,195 MW", or null while the interval is unavailable. */
export function intervalText(iv: IntervalOut | null | undefined, signed = false): string | null {
  if (!iv || iv.low === null || iv.high === null) return null;
  return `${Math.round(iv.level * 100)}% range: ${fmtNumber(iv.low, signed)} to ${fmtNumber(iv.high, signed)} MW`;
}