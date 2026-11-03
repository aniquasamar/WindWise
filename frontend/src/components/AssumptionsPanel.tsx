import type { MetaOut } from "../api/types";
import { fmtClock, fmtInstantDay } from "../lib/format";

interface Props {
  meta: MetaOut | null;
  id: string;
}

export function AssumptionsPanel({ meta, id }: Props) {
  return (
    <section id={id} className="assumptions" aria-label="Assumptions">
      <h2>Assumptions behind every number</h2>
      {meta === null ? (
        <p className="muted">Loading assumptions…</p>
      ) : (
        <>
          <ol>
            {meta.assumptions.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ol>
          <dl className="facts">
            <div>
              <dt>Data source</dt>
              <dd>{meta.data.source}</dd>
            </div>
            <div>
              <dt>Data retrieved</dt>
              <dd>
                {fmtInstantDay(meta.data.retrieved_at)} {meta.data.retrieved_at.slice(0, 4)}
              </dd>
            </div>
            <div>
              <dt>Contents</dt>
              <dd>
                {meta.data.rows_actuals.toLocaleString("en-GB")} half-hourly actuals and{" "}
                {meta.data.rows_forecasts.toLocaleString("en-GB")} forecast values from {meta.data.runs} runs
              </dd>
            </div>
            {meta.data.unscheduled_runs.length > 0 ? (
              <div>
                <dt>Unusual run times</dt>
                <dd>
                  {meta.data.unscheduled_runs.map((r) => `${fmtInstantDay(r)} at ${fmtClock(r)}`).join(", ")} (published later than
                  the usual schedule)
                </dd>
              </div>
            ) : null}
          </dl>
        </>
      )}
    </section>
  );
}