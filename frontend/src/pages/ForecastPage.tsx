import { useMemo, useState } from "react";
import { apiUrl } from "../api/client";
import { useApi } from "../api/hooks";
import type { ByDayOut, ForecastOut, MetaOut } from "../api/types";
import { DataTable } from "../components/DataTable";
import { ErrorState, Skeleton } from "../components/Feedback";
import { KpiCard } from "../components/KpiCard";
import { LineChart } from "../components/LineChart";
import type { ChartSeries } from "../components/LineChart";
import { Select } from "../components/Select";
import { downloadCsv, toCsv } from "../lib/csv";
import { clampDate, cutoffOptions, dayResult, isIsoDate, largestMissDate, peakPoint, shiftDate } from "../lib/derive";
import { fmtClock, fmtDateLong, fmtDateShort, fmtDuration, fmtInstantDay, fmtMw, fmtNumber, fmtPct } from "../lib/format";
import { setParams, useRoute } from "../lib/router";

function pick(value: string | null, allowed: string[], fallback: string): string {
  return value !== null && allowed.includes(value) ? value : fallback;
}

interface LegendProps {
  label: string;
  color: string;
  line: "solid" | "dashed" | "dotted";
  pressed: boolean;
  disabled?: boolean;
  note?: string;
  onToggle?: () => void;
}

function LegendToggle({ label, color, line, pressed, disabled = false, note, onToggle }: LegendProps) {
  const fixed = onToggle === undefined;
  return (
    <button
      type="button"
      className="legend-btn"
      aria-pressed={fixed ? undefined : pressed}
      disabled={disabled || fixed}
      onClick={onToggle}
      title={note}
    >
      <span className="swatch" style={{ borderTopColor: color, borderTopStyle: line }} aria-hidden="true" />
      <span>{label}</span>
      {note && disabled ? <span className="legend-note">{note}</span> : null}
    </button>
  );
}

export function ForecastPage({ meta }: { meta: MetaOut | null }) {
  const route = useRoute();
  const min = meta?.window.first_delivery ?? "2026-01-02";
  const max = meta?.window.last_delivery ?? "2026-02-01";
  const cutoffs = useMemo(
    () => (meta ? cutoffOptions(meta.allowed.cutoff_min, meta.allowed.cutoff_max, meta.allowed.cutoff_step_minutes) : ["09:00"]),
    [meta],
  );
  const confidences = meta ? meta.allowed.confidence.map(String) : ["0.9"];
  const cutoff = pick(route.params.get("cutoff"), cutoffs, meta?.defaults.cutoff ?? "09:00");
  const confidence = pick(route.params.get("confidence"), confidences, String(meta?.defaults.confidence ?? 0.9));

  // With no date chosen, start on the day with the largest miss: that is where the forecast matters most.
  const requested = route.params.get("date");
  const hasDate = isIsoDate(requested);
  const byDay = useApi<ByDayOut>(hasDate ? null : apiUrl("/api/v1/accuracy/by-day", { cutoff }));
  const suggested = largestMissDate(byDay.data?.days ?? []);
  const date = hasDate ? clampDate(requested, min, max) : suggested ?? (byDay.error ? min : null);
  const usingSuggestion = !hasDate && suggested !== null;

  const forecast = useApi<ForecastOut>(date ? apiUrl("/api/v1/forecast", { delivery_date: date, cutoff, confidence }) : null);
  const data = forecast.data;
  const [show, setShow] = useState({ actual: true, firm: true, corrected: false, baseline: false });

  const xLabels = useMemo(() => (data ? data.points.map((p) => fmtClock(p.time)) : []), [data]);
  const series = useMemo<ChartSeries[]>(() => {
    if (!data) return [];
    const pts = data.points;
    const list: ChartSeries[] = [
      { id: "forecast", label: "Forecast at the cutoff", color: "var(--forecast)", values: pts.map((p) => p.forecast_mw), width: 3 },
    ];
    if (show.firm && data.buffer.status === "ok") {
      list.push({ id: "firm", label: "Firm wind", color: "var(--firm)", line: "dashed", values: pts.map((p) => p.firm_mw) });
    }
    if (show.corrected && data.benchmark.status === "ok") {
      list.push({ id: "corrected", label: "Bias-corrected (experimental)", color: "var(--corrected)", line: "dotted", values: pts.map((p) => p.corrected_mw) });
    }
    if (show.baseline) {
      list.push({ id: "baseline", label: "Same hour 48 h earlier", color: "var(--baseline)", line: "dotted", values: pts.map((p) => p.baseline_mw) });
    }
    if (show.actual) {
      list.push({ id: "actual", label: "Actual wind", color: "var(--actual)", values: pts.map((p) => p.actual_mw), width: 3 });
    }
    return list;
  }, [data, show]);

  const setDate = (iso: string) => setParams({ date: clampDate(iso, min, max) });
  const confPct = Math.round(Number(confidence) * 100);

  return (
    <div className={forecast.loading && data ? "is-loading" : undefined} aria-busy={forecast.loading}>
      <header className="page-head">
        <h1>What did I know when I had to decide?</h1>
        <p className="lede">
          {data ? (
            <>
              Buying for delivery on <strong>{fmtDateLong(data.delivery_date)}</strong>. The decision is made on{" "}
              {fmtDateShort(data.decision_date)} at {data.cutoff_local} UK time, so this is the newest forecast that existed by then.
            </>
          ) : (
            "Pick a delivery day to see the newest forecast that existed when the buying decision had to be made."
          )}
        </p>
      </header>

      <div className="controls">
        <div className="date-nav">
          <button type="button" className="icon-btn" aria-label="Previous day" disabled={date === null || date <= min} onClick={() => date && setDate(shiftDate(date, -1))}>
            ‹
          </button>
          <label className="field">
            <span className="field-label">Delivery date</span>
            <input
              type="date"
              value={date ?? ""}
              min={min}
              max={max}
              onChange={(e) => {
                if (isIsoDate(e.target.value)) setDate(e.target.value);
              }}
            />
          </label>
          <button type="button" className="icon-btn" aria-label="Next day" disabled={date === null || date >= max} onClick={() => date && setDate(shiftDate(date, 1))}>
            ›
          </button>
        </div>
        <Select label="Decision cutoff (UK time)" value={cutoff} options={cutoffs.map((c) => ({ value: c, label: c }))} onChange={(v) => setParams({ cutoff: v })} />
        <Select
          label="Buffer confidence"
          value={confidence}
          options={confidences.map((c) => ({ value: c, label: `${Math.round(Number(c) * 100)}%` }))}
          onChange={(v) => setParams({ confidence: v })}
        />
      </div>
      {usingSuggestion ? <p className="note">Showing the day with the largest miss in January. Pick any date to explore.</p> : null}

      {forecast.error ? (
        <ErrorState error={forecast.error} onRetry={forecast.reload} />
      ) : !data ? (
        <>
          <div className="kpi-grid">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} height={104} label="Loading figures" />
            ))}
          </div>
          <Skeleton height={420} label="Loading chart" />
        </>
      ) : (
        <ForecastBody data={data} show={show} setShow={setShow} series={series} xLabels={xLabels} confPct={confPct} cutoff={cutoff} />
      )}
    </div>
  );
}

interface BodyProps {
  data: ForecastOut;
  show: { actual: boolean; firm: boolean; corrected: boolean; baseline: boolean };
  setShow: (next: { actual: boolean; firm: boolean; corrected: boolean; baseline: boolean }) => void;
  series: ChartSeries[];
  xLabels: string[];
  confPct: number;
  cutoff: string;
}

function ForecastBody({ data, show, setShow, series, xLabels, confPct, cutoff }: BodyProps) {
  const peak = peakPoint(data.points);
  const run = data.runs_used[0];
  const result = dayResult(data.points);
  const bufferOk = data.buffer.status === "ok" && data.buffer.buffer_mw !== null;
  const correctedOk = data.benchmark.status === "ok";
  const toggle = (key: keyof BodyProps["show"]) => setShow({ ...show, [key]: !show[key] });

  return (
    <>
      <div className="kpi-grid">
        <KpiCard label="Peak forecast" value={fmtMw(data.forecast_summary.peak_mw)} hint={peak ? `at ${fmtClock(peak.time)}` : undefined} />
        <KpiCard label="Average forecast" value={fmtMw(data.forecast_summary.mean_mw)} hint="across the 24 hours" />
        {run ? (
          <KpiCard
            label="Forecast used"
            value={`${fmtClock(run.publish_time)} run`}
            hint={`Published ${fmtInstantDay(run.publish_time)}, ${fmtDuration(run.age_hours_at_cutoff)} before the ${data.cutoff_local} cutoff`}
            info="The most recent forecast published at or before the cutoff. Later forecasts are never used."
          />
        ) : (
          <KpiCard label="Forecast used" value="None available" hint="No forecast existed at the cutoff" tone="warn" />
        )}
        {bufferOk ? (
          <KpiCard
            label={`Buffer at ${confPct}%`}
            value={fmtMw(data.buffer.buffer_mw)}
            hint={`Subtract from the forecast. Based on ${data.buffer.history_days} earlier days`}
            info="How far actual wind fell short of the forecast in the worst tenth of hours on earlier days. Only days before this decision are used."
          />
        ) : (
          <KpiCard
            label={`Buffer at ${confPct}%`}
            value="Not enough history"
            hint={`Needs ${data.buffer.min_history_days} earlier days; ${data.buffer.history_days} available`}
            tone="warn"
          />
        )}
      </div>

      <section className="card" aria-labelledby="chart-title">
        <div className="card-head">
          <h2 id="chart-title">Wind forecast for {fmtDateLong(data.delivery_date)}</h2>
          <div className="legend" role="group" aria-label="Chart lines">
            <LegendToggle label="Forecast at the cutoff" color="var(--forecast)" line="solid" pressed />
            <LegendToggle label="Actual wind" color="var(--actual)" line="solid" pressed={show.actual} onToggle={() => toggle("actual")} />
            <LegendToggle
              label="Firm wind"
              color="var(--firm)"
              line="dashed"
              pressed={show.firm && bufferOk}
              disabled={!bufferOk}
              note="needs more history"
              onToggle={() => toggle("firm")}
            />
            <LegendToggle
              label="Bias-corrected (experimental)"
              color="var(--corrected)"
              line="dotted"
              pressed={show.corrected && correctedOk}
              disabled={!correctedOk}
              note="needs more history"
              onToggle={() => toggle("corrected")}
            />
            <LegendToggle label="Same hour 48 h earlier" color="var(--baseline)" line="dotted" pressed={show.baseline} onToggle={() => toggle("baseline")} />
          </div>
        </div>

        <LineChart
          xLabels={xLabels}
          series={series}
          ariaLabel={`Hourly wind forecast for ${fmtDateLong(data.delivery_date)}, in megawatts`}
          yFormat={(v) => fmtNumber(v)}
          title={(i) => `Hour starting ${xLabels[i]} (UK time)`}
          gap={show.actual ? { a: "forecast", b: "actual", aboveColor: "var(--over-soft)", belowColor: "var(--under-soft)" } : undefined}
          extraRows={(i) => {
            const p = data.points[i];
            return show.actual && p.error_mw !== null
              ? [{ label: "Error", value: `${fmtMw(p.error_mw, true)} (${p.error_mw > 0 ? "too high" : "too low"})` }]
              : [];
          }}
        />
        <p className="chart-axis-note">Megawatts (MW). Shaded area: orange where the forecast was above actual wind, blue where it was below.</p>

        {show.actual ? (
          result.scoredHours > 0 && result.meanError !== null && result.meanActual !== null ? (
            <div className={`banner ${result.meanError > 0 ? "banner--over" : "banner--under"}`}>
              <strong>How the day turned out.</strong> The forecast averaged {fmtMw(Math.abs(result.meanError))}{" "}
              <strong>{result.meanError > 0 ? "above" : "below"}</strong> actual wind ({fmtPct(result.meanError / result.meanActual, 0, true)} of actual).{" "}
              {result.firmHeldHours !== null
                ? `With the buffer, actual wind met the firm-wind level in ${result.firmHeldHours} of ${result.firmHours} hours.`
                : "No buffer was available for this day because there were not enough earlier days."}
            </div>
          ) : (
            <p className="note">No actual wind data is available for this day yet.</p>
          )
        ) : (
          <p className="note">Actual wind is hidden. Switch it on in the legend to see how the day turned out.</p>
        )}
      </section>

      <details className="card table-card">
        <summary>Show the hourly numbers</summary>
        <div className="table-actions">
          <button
            type="button"
            className="btn btn--secondary"
            onClick={() =>
              downloadCsv(
                `windwise-forecast-${data.delivery_date}-cutoff-${cutoff.replace(":", "")}.csv`,
                toCsv([
                  ["hour_start_utc", "forecast_mw", "actual_mw", "error_mw", "horizon_h", "firm_wind_mw", "baseline_48h_mw", "bias_corrected_mw"],
                  ...data.points.map((p) => [p.time, p.forecast_mw, p.actual_mw, p.error_mw, p.horizon_h, p.firm_mw, p.baseline_mw, p.corrected_mw]),
                ]),
              )
            }
          >
            Download CSV
          </button>
        </div>
        <DataTable
          caption={`Hourly wind figures for ${fmtDateLong(data.delivery_date)}`}
          headers={["Hour (UK)", "Forecast", "Actual", "Error", "Firm wind", "Baseline"]}
          rows={data.points.map((p) => [
            fmtClock(p.time),
            fmtNumber(p.forecast_mw),
            fmtNumber(p.actual_mw),
            fmtNumber(p.error_mw, true),
            fmtNumber(p.firm_mw),
            fmtNumber(p.baseline_mw),
          ])}
        />
      </details>
    </>
  );
}