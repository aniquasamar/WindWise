import { useState } from "react";
import type { ReactNode } from "react";
import { apiUrl } from "../api/client";
import type { ApiError } from "../api/client";
import { useApi } from "../api/hooks";
import type {
  BenchmarksOut, BufferBacktestOut, ByDayOut, ByHourOut, ByLevelOut, DistributionOut, HorizonOut, RunsOut,
} from "../api/types";
import { backtestCaption, benchmarkCaption, dayCaption, distributionCaption, horizonCaption, hourCaption, levelCaption, runsCaption } from "../lib/captions";
import { fmtDateLong, fmtDateShort, fmtMw, fmtNumber, fmtPct } from "../lib/format";
import { BarChart } from "./BarChart";
import { ErrorState, Skeleton } from "./Feedback";
import { Segmented } from "./Segmented";

interface LegendItem {
  label: string;
  color: string;
  kind: "bar" | "dot";
}

interface CardState {
  loading: boolean;
  error: ApiError | null;
  reload: () => void;
  data: unknown;
}

interface CardProps {
  id: string;
  title: string;
  takeaway?: string | null;
  state: CardState;
  legend?: LegendItem[];
  note?: string;
  actions?: ReactNode;
  wide?: boolean;
  children: ReactNode;
}

function ChartCard({ id, title, takeaway, state, legend, note, actions, wide = false, children }: CardProps) {
  return (
    <section className={`card chart-card${wide ? " chart-card--wide" : ""}`} aria-labelledby={`${id}-title`} data-chart={id}>
      <div className="card-head">
        <h3 id={`${id}-title`}>{title}</h3>
        {actions}
      </div>
      {state.error ? (
        <ErrorState error={state.error} onRetry={state.reload} />
      ) : state.data === null ? (
        <Skeleton height={300} label={`Loading: ${title}`} />
      ) : (
        <>
          {takeaway ? <p className="takeaway">{takeaway}</p> : null}
          {children}
          {legend ? (
            <ul className="mini-legend" aria-label="Key">
              {legend.map((item) => (
                <li key={item.label}>
                  <span className={`mini-swatch mini-swatch--${item.kind}`} style={{ background: item.kind === "bar" ? item.color : "transparent", borderColor: item.color }} aria-hidden="true" />
                  {item.label}
                </li>
              ))}
            </ul>
          ) : null}
          {note ? <p className="chart-axis-note">{note}</p> : null}
        </>
      )}
    </section>
  );
}

const signColor = (v: number | null) => (v !== null && v < 0 ? "var(--under)" : "var(--over)");
const hh = (hour: number) => `${String(hour).padStart(2, "0")}:00`;
const mw = (v: number) => fmtNumber(v);

interface Common {
  cutoff: string;
}

export function DaySection({ cutoff }: Common) {
  const r = useApi<ByDayOut>(apiUrl("/api/v1/accuracy/by-day", { cutoff }));
  const days = r.data?.days ?? [];
  return (
    <ChartCard id="chart-day" title="Average error by delivery day" takeaway={r.data ? dayCaption(days) : null} state={r} wide
      legend={[{ label: "Forecast too high", color: "var(--over)", kind: "bar" }, { label: "Forecast too low", color: "var(--under)", kind: "bar" }]}
      note="Megawatts (MW): forecast minus actual, averaged over each day's 24 hours.">
      <BarChart
        bars={days.map((d) => ({ label: fmtDateShort(d.delivery_date), value: d.metrics.bias, color: signColor(d.metrics.bias) }))}
        ariaLabel="Average forecast error for each delivery day, in megawatts"
        yFormat={mw}
        xTickEvery={5}
        title={(i) => fmtDateLong(days[i].delivery_date)}
        rows={(i) => [
          { label: "Forecast average", value: fmtMw(days[i].forecast_mean) },
          { label: "Actual average", value: fmtMw(days[i].actual_mean) },
          { label: "Average error", value: fmtMw(days[i].metrics.bias, true) },
          { label: "Typical miss", value: fmtMw(days[i].metrics.mae) },
        ]}
      />
    </ChartCard>
  );
}

export function HourSection({ cutoff }: Common) {
  const r = useApi<ByHourOut>(apiUrl("/api/v1/accuracy/by-hour", { cutoff }));
  const hours = r.data?.hours ?? [];
  return (
    <ChartCard id="chart-hour" title="Error by hour of day" takeaway={r.data ? hourCaption(hours) : null} state={r}
      legend={[{ label: "Average error", color: "var(--over)", kind: "bar" }, { label: "Buffer for 9 hours in 10", color: "var(--firm)", kind: "dot" }]}
      note="Hours are UK time. Megawatts (MW).">
      <BarChart
        bars={hours.map((h) => ({ label: String(h.hour).padStart(2, "0"), value: h.metrics.bias, color: signColor(h.metrics.bias) }))}
        overlay={{ color: "var(--firm)", values: hours.map((h) => h.metrics.p90_signed) }}
        ariaLabel="Average forecast error by hour of day, with the buffer for nine hours in ten, in megawatts"
        yFormat={mw}
        xTickEvery={3}
        xTickLabel={(i) => hh(hours[i].hour)}
        title={(i) => `Hour starting ${hh(hours[i].hour)}`}
        rows={(i) => [
          { label: "Average error", value: fmtMw(hours[i].metrics.bias, true) },
          { label: "Buffer (9 in 10)", value: fmtMw(hours[i].metrics.p90_signed, true), color: "var(--firm)" },
          { label: "Typical miss", value: fmtMw(hours[i].metrics.mae) },
        ]}
      />
    </ChartCard>
  );
}

export function LevelSection({ cutoff }: Common) {
  const r = useApi<ByLevelOut>(apiUrl("/api/v1/accuracy/by-forecast-level", { cutoff }));
  const levels = r.data?.levels ?? [];
  return (
    <ChartCard id="chart-level" title="Error by size of the forecast" takeaway={r.data ? levelCaption(levels) : null} state={r}
      legend={[{ label: "Average error", color: "var(--over)", kind: "bar" }, { label: "Buffer for 9 hours in 10", color: "var(--firm)", kind: "dot" }]}
      note="Hours are grouped into thirds by the size of the forecast, which is known when the decision is made. Megawatts (MW).">
      <BarChart
        bars={levels.map((l) => ({ label: `${l.label[0].toUpperCase()}${l.label.slice(1)} forecast`, value: l.metrics.bias, color: signColor(l.metrics.bias) }))}
        overlay={{ color: "var(--firm)", values: levels.map((l) => l.metrics.p90_signed), connect: false }}
        valueLabel={(v) => fmtNumber(v, true)}
        gap={0.45}
        ariaLabel="Average forecast error and buffer by size of the forecast, in megawatts"
        yFormat={mw}
        title={(i) => `${levels[i].label[0].toUpperCase()}${levels[i].label.slice(1)} forecasts (${fmtNumber(levels[i].forecast_min)} to ${fmtNumber(levels[i].forecast_max)} MW)`}
        rows={(i) => [
          { label: "Average error", value: fmtMw(levels[i].metrics.bias, true) },
          { label: "Buffer (9 in 10)", value: fmtMw(levels[i].metrics.p90_signed, true), color: "var(--firm)" },
          { label: "Typical miss", value: fmtMw(levels[i].metrics.mae) },
          { label: "Hours", value: fmtNumber(levels[i].metrics.n) },
        ]}
      />
    </ChartCard>
  );
}

export function DistributionSection({ cutoff }: Common) {
  const r = useApi<DistributionOut>(apiUrl("/api/v1/accuracy/distribution", { cutoff }));
  const d = r.data;
  const bins = d?.bins ?? [];
  const markers = [];
  if (d && bins.length) {
    if (d.p10 !== null) markers.push({ position: (d.p10 - bins[0].lower) / d.bin_width_mw, label: `P10 ${fmtNumber(d.p10, true)}`, color: "var(--under-text)" });
    if (d.p90 !== null) markers.push({ position: (d.p90 - bins[0].lower) / d.bin_width_mw, label: `P90 ${fmtNumber(d.p90, true)}`, color: "var(--over-text)" });
  }
  const every = Math.max(1, Math.ceil(bins.length / 7));
  return (
    <ChartCard id="chart-distribution" title="How big are the misses? (all hours)" takeaway={d ? distributionCaption(d) : null} state={r} wide
      note="Number of hours at each size of error, in megawatts (MW). Negative means the forecast was too low.">
      <BarChart
        bars={bins.map((b) => ({ label: fmtNumber(b.lower), value: b.count, color: (b.lower + b.upper) / 2 > 0 ? "var(--over)" : "var(--under)" }))}
        vMarkers={markers}
        gap={0.06}
        xTickEvery={every}
        ariaLabel="Number of hours at each size of forecast error, in megawatts"
        yFormat={mw}
        title={(i) => `${fmtNumber(bins[i].lower, true)} to ${fmtNumber(bins[i].upper, true)} MW`}
        rows={(i) => [{ label: "Hours", value: fmtNumber(bins[i].count) }, { label: "Share of all hours", value: d && d.n ? fmtPct(bins[i].count / d.n, 1) : "\u2013" }]}
      />
    </ChartCard>
  );
}

export function BacktestSection({ cutoff, confidence }: Common & { confidence: string }) {
  const r = useApi<BufferBacktestOut>(apiUrl("/api/v1/buffer/backtest", { cutoff, confidence }));
  const b = r.data;
  const days = b?.days ?? [];
  const pct = Math.round(Number(confidence) * 100);
  return (
    <ChartCard id="chart-backtest" title="Did the buffer hold, day by day?" takeaway={b ? backtestCaption(b) : null} state={r} wide
      note={`Share of each day's hours in which actual wind was at least the forecast minus the buffer, using only earlier days to set the buffer. The line is the ${pct}% promised.`}
      legend={[{ label: "Held for every hour", color: "var(--firm)", kind: "bar" }, { label: "Missed in some hours", color: "var(--over)", kind: "bar" }]}>
      <BarChart
        bars={days.map((d) => ({ label: fmtDateShort(d.delivery_date), value: (d.covered / d.hours) * 100, color: d.covered === d.hours ? "var(--firm)" : "var(--over)" }))}
        refLines={[{ value: pct, label: `Promised ${pct}%`, color: "var(--muted)" }]}
        ariaLabel="Share of hours each day in which the buffer held"
        yFormat={(v) => `${fmtNumber(v)}%`}
        domainMax={100}
        xTickEvery={3}
        title={(i) => fmtDateLong(days[i].delivery_date)}
        rows={(i) => [
          { label: "Hours covered", value: `${days[i].covered} of ${days[i].hours}` },
          { label: "Buffer used", value: fmtMw(days[i].buffer_mw) },
          { label: "Earlier days used", value: fmtNumber(days[i].history_days) },
          { label: "Average error that day", value: fmtMw(days[i].mean_error_mw, true) },
        ]}
      />
    </ChartCard>
  );
}

export function BenchmarkSection({ cutoff }: Common) {
  const r = useApi<BenchmarksOut>(apiUrl("/api/v1/accuracy/benchmarks", { cutoff }));
  const b = r.data;
  const ratio = b?.bias_corrected.find((x) => x.method === "ratio");
  const offset = b?.bias_corrected.find((x) => x.method === "offset");
  const items = ratio && offset
    ? [
        { label: "Official forecast", m: ratio.official, color: "var(--forecast)" },
        { label: "Corrected: ratio", m: ratio.corrected, color: "var(--corrected)" },
        { label: "Corrected: offset", m: offset.corrected, color: "var(--corrected)" },
      ]
    : [];
  return (
    <ChartCard id="chart-benchmark" title="Experiment: correcting the forecast with recent days" takeaway={b ? benchmarkCaption(b) : null} state={r}
      legend={[{ label: "Typical miss (MAE)", color: "var(--forecast)", kind: "bar" }, { label: "Big-miss measure (RMSE)", color: "var(--actual)", kind: "dot" }]}
      note={ratio ? `Compared on the same ${ratio.days_scored} days that have at least ${ratio.min_days} earlier days. ${b?.experimental_notice ?? ""}` : undefined}>
      <BarChart
        bars={items.map((x) => ({ label: x.label, value: x.m.mae, color: x.color }))}
        overlay={{ color: "var(--actual)", values: items.map((x) => x.m.rmse), connect: false }}
        valueLabel={mw}
        gap={0.45}
        ariaLabel="Typical miss and big-miss measure for the official forecast and two experimental corrections, in megawatts"
        yFormat={mw}
        title={(i) => items[i].label}
        rows={(i) => [
          { label: "Typical miss (MAE)", value: fmtMw(items[i].m.mae) },
          { label: "Big-miss measure (RMSE)", value: fmtMw(items[i].m.rmse), color: "var(--actual)" },
          { label: "Average error", value: fmtMw(items[i].m.bias, true) },
        ]}
      />
    </ChartCard>
  );
}

export function HorizonSection({ cutoff }: Common) {
  const [view, setView] = useState("full");
  const r = useApi<HorizonOut>(apiUrl("/api/v1/accuracy/horizon", { cutoff, view }));
  const h = r.data;
  const buckets = h?.buckets ?? [];
  const short = (label: string, elapsed: boolean) => (elapsed ? "Elapsed" : label.replace(" to ", "\u2013"));
  return (
    <ChartCard id="chart-horizon" title="Does the miss grow with the horizon?" takeaway={h ? horizonCaption(h) : null} state={r}
      actions={<Segmented label="View" value={view} onChange={setView} options={[{ value: "full", label: "All runs" }, { value: "decision", label: "Forecast used" }]} />}
      legend={[{ label: "Typical miss (MAE)", color: "var(--forecast)", kind: "bar" }, { label: "Average error", color: "var(--over)", kind: "dot" }]}
      note={h?.note}>
      <BarChart
        bars={buckets.map((b) => ({ label: short(b.label, b.elapsed), value: b.metrics.mae, color: b.elapsed ? "var(--baseline)" : "var(--forecast)" }))}
        overlay={{ color: "var(--over)", values: buckets.map((b) => b.metrics.bias), connect: false }}
        gap={0.35}
        ariaLabel="Typical miss and average error by forecast horizon, in megawatts"
        yFormat={mw}
        title={(i) => buckets[i].label}
        rows={(i) => [
          { label: "Typical miss (MAE)", value: fmtMw(buckets[i].metrics.mae) },
          { label: "Average error", value: fmtMw(buckets[i].metrics.bias, true), color: "var(--over)" },
          { label: "Hours counted", value: fmtNumber(buckets[i].metrics.n) },
        ]}
      />
    </ChartCard>
  );
}

export function RunsSection() {
  const r = useApi<RunsOut>(apiUrl("/api/v1/accuracy/runs"));
  const d = r.data;
  const results = d?.results ?? [];
  return (
    <ChartCard id="chart-runs" title="Does it matter which run you act on?" takeaway={d ? runsCaption(d) : null} state={r}
      legend={[{ label: "Typical miss (MAE)", color: "var(--forecast)", kind: "bar" }, { label: "Big-miss measure (RMSE)", color: "var(--actual)", kind: "dot" }]}
      note="Each cutoff (UK time) uses the newest run published before it. The highlighted bar is the default 09:00.">
      <BarChart
        bars={results.map((x) => ({ label: x.cutoff, value: x.metrics.mae, color: d && x.cutoff === d.default_cutoff ? "var(--brand)" : "var(--forecast)" }))}
        overlay={{ color: "var(--actual)", values: results.map((x) => x.metrics.rmse), connect: false }}
        valueLabel={mw}
        gap={0.35}
        ariaLabel="Typical miss and big-miss measure for each decision cutoff, in megawatts"
        yFormat={mw}
        title={(i) => `Cutoff ${results[i].cutoff} UK time`}
        rows={(i) => [
          { label: "Run used (UTC)", value: results[i].runs_used.join(", ") || "none" },
          { label: "Typical miss (MAE)", value: fmtMw(results[i].metrics.mae) },
          { label: "Big-miss measure (RMSE)", value: fmtMw(results[i].metrics.rmse), color: "var(--actual)" },
          { label: "Typical miss vs 09:00", value: results[i].mae_change_vs_default === null ? "\u2013" : fmtPct(results[i].mae_change_vs_default, 1, true) },
        ]}
      />
    </ChartCard>
  );
}