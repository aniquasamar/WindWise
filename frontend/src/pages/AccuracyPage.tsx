import { useMemo } from "react";
import { apiUrl } from "../api/client";
import { useApi } from "../api/hooks";
import type { IntervalsOut, MetaOut, SummaryOut } from "../api/types";
import {
  BacktestSection, BenchmarkSection, DaySection, DistributionSection, HorizonSection, HourSection, LevelSection, RunsSection,
} from "../components/AccuracySections";
import { ErrorState, Skeleton } from "../components/Feedback";
import { KpiCard } from "../components/KpiCard";
import { Select } from "../components/Select";
import { intervalText } from "../lib/captions";
import { cutoffOptions } from "../lib/derive";
import { fmtMw, fmtNumber, fmtOdds, fmtPct } from "../lib/format";
import { setParams, useRoute } from "../lib/router";

function pick(value: string | null, allowed: string[], fallback: string): string {
  return value !== null && allowed.includes(value) ? value : fallback;
}

export function AccuracyPage({ meta }: { meta: MetaOut | null }) {
  const route = useRoute();
  const cutoffs = useMemo(
    () => (meta ? cutoffOptions(meta.allowed.cutoff_min, meta.allowed.cutoff_max, meta.allowed.cutoff_step_minutes) : ["09:00"]),
    [meta],
  );
  const confidences = meta ? meta.allowed.confidence.map(String) : ["0.9"];
  const cutoff = pick(route.params.get("cutoff"), cutoffs, meta?.defaults.cutoff ?? "09:00");
  const confidence = pick(route.params.get("confidence"), confidences, String(meta?.defaults.confidence ?? 0.9));
  const summary = useApi<SummaryOut>(apiUrl("/api/v1/accuracy/summary", { cutoff, confidence }));
  const data = summary.data;

  return (
    <div className={summary.loading && data ? "is-loading" : undefined} aria-busy={summary.loading}>
      <header className="page-head">
        <h1>How much should I trust it?</h1>
        <p className="lede">
          Every forecast the buyer would have used in January, compared with what the wind actually produced. Errors are forecast minus
          actual, so a positive number means the forecast was too high.
        </p>
      </header>

      <div className="controls">
        <Select
          label="Buffer confidence"
          value={confidence}
          options={confidences.map((c) => ({ value: c, label: `${Math.round(Number(c) * 100)}%` }))}
          onChange={(v) => setParams({ confidence: v })}
        />
        <Select label="Decision cutoff (UK time)" value={cutoff} options={cutoffs.map((c) => ({ value: c, label: c }))} onChange={(v) => setParams({ cutoff: v })} />
      </div>

      {summary.error ? (
        <ErrorState error={summary.error} onRetry={summary.reload} />
      ) : !data ? (
        <>
          <Skeleton height={190} label="Loading the buffer" />
          <div className="kpi-grid">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} height={104} label="Loading figures" />
            ))}
          </div>
        </>
      ) : (
        <SummaryBody data={data} cutoff={cutoff} confidence={confidence} />
      )}
    </div>
  );
}

function SummaryBody({ data, cutoff, confidence }: { data: SummaryOut; cutoff: string; confidence: string }) {
  const intervals = useApi<IntervalsOut>(apiUrl("/api/v1/accuracy/intervals", { cutoff, confidence }));
  const iv = intervals.data;
  const m = data.metrics;
  const conf = data.confidence;
  const confPct = Math.round(conf * 100);
  const buffer = data.buffer_in_sample.buffer_mw;
  const bt = data.backtest;
  const short = bt.coverage !== null && bt.coverage < conf - 0.01;

  return (
    <>
      <section className="callout" aria-labelledby="buffer-title">
        <p className="callout-eyebrow">The practical answer</p>
        {buffer !== null ? (
          <h2 id="buffer-title">
            To be covered {fmtOdds(conf)}, plan on the forecast minus <span className="callout-number">{fmtMw(buffer)}</span>.
          </h2>
        ) : (
          <h2 id="buffer-title">There is not enough data to suggest a buffer.</h2>
        )}
        {bt.coverage !== null ? (
          <p>
            <strong>Tested honestly:</strong> applied day by day using only earlier data, a {confPct}% buffer held in{" "}
            <strong>{fmtPct(bt.coverage, 1)}</strong> of hours ({bt.days_scored} days, {bt.hours_scored} hours).{" "}
            {short
              ? `That is below the ${confPct}% it promised, so treat the buffer as a minimum, not a guarantee.`
              : `That is in line with the ${confPct}% promised.`}
          </p>
        ) : null}
        {iv && intervalText(iv.buffer) ? (
          <p className="muted small">
            How certain is that number? Resampling whole days gives a {intervalText(iv.buffer)} for the buffer.
          </p>
        ) : null}
        <p className="muted small">
          The first {bt.days_skipped} days could not be tested because a buffer needs {bt.min_history_days} earlier days of history. Demand
          and prices are outside this pilot, so this is a haircut on wind, not a purchase quantity.
        </p>
      </section>

      <div className="kpi-grid kpi-grid--wide">
        <KpiCard
          label="Average error (bias)"
          value={fmtMw(m.bias, true)}
          hint={m.bias !== null && m.bias > 0 ? "Forecast is too high on average" : "Forecast is too low on average"}
          range={intervalText(iv?.bias, true) ?? undefined}
          tone={m.bias !== null && m.bias > 0 ? "over" : "under"}
          info="The average of forecast minus actual. A positive number means the forecast promised more wind than arrived."
        />
        <KpiCard label="Typical miss (MAE)" value={fmtMw(m.mae)} hint={`${fmtPct(m.nmae)} of average wind`} range={intervalText(iv?.mae) ?? undefined} info="The average size of the error, ignoring direction." />
        <KpiCard label="Big-miss measure (RMSE)" value={fmtMw(m.rmse)} hint="Counts large misses extra" range={intervalText(iv?.rmse) ?? undefined} info="Like the typical miss, but large errors count for more. A big gap between this and the typical miss means occasional large misses." />
        <KpiCard label="One bad hour in ten (P90)" value={fmtMw(m.p90_abs)} hint="The miss is bigger than this in 10% of hours" info="The 90th percentile of the absolute error." />
        <KpiCard label="Hours forecast too high" value={fmtPct(m.over_share)} hint={`of ${fmtNumber(data.counts.hours_scored)} hours`} tone="over" />
        <KpiCard
          label="Better than a lazy guess by"
          value={fmtPct(data.baseline.skill_mae)}
          hint="Versus repeating the same hour two days earlier (typical miss)"
          info="1 minus the forecast's typical miss divided by the baseline's typical miss. Zero means no better than the baseline."
        />
      </div>

      <section className="card" aria-labelledby="insights-title">
        <h2 id="insights-title">What this means</h2>
        <ul className="insights">
          {data.insights.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </section>

      <section className="block" aria-labelledby="where-title">
        <h2 id="where-title" className="block-title">Where and when the forecast misses</h2>
        <div className="chart-grid">
          <DaySection cutoff={cutoff} />
          <HourSection cutoff={cutoff} />
          <LevelSection cutoff={cutoff} />
          <DistributionSection cutoff={cutoff} />
        </div>
      </section>

      <section className="block" aria-labelledby="trust-title">
        <h2 id="trust-title" className="block-title">Can the buffer be trusted?</h2>
        <div className="chart-grid">
          <BacktestSection cutoff={cutoff} confidence={confidence} />
          <BenchmarkSection cutoff={cutoff} />
        </div>
      </section>

      <section className="block" aria-labelledby="timing-title">
        <h2 id="timing-title" className="block-title">Does timing matter?</h2>
        <div className="chart-grid">
          <HorizonSection cutoff={cutoff} />
          <RunsSection />
        </div>
      </section>

      <section className="card honesty" aria-labelledby="honesty-title">
        <h2 id="honesty-title">What this does not tell you</h2>
        <ul>
          <li>It covers {data.range.n_days} days of one winter month. Errors cluster by day, so the real sample is closer to {data.range.n_days} independent days than to {fmtNumber(data.counts.hours_scored)} hours.</li>
          <li>The cause of the persistent over-forecast is not established here. It may reflect what the two published series cover.</li>
          <li>Demand and prices are not included, so the cost of being wrong in either direction is not measured.</li>
        </ul>
      </section>
    </>
  );
}