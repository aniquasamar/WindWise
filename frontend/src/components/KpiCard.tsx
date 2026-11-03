export type Tone = "neutral" | "over" | "under" | "warn";

interface Props {
  label: string;
  value: string;
  hint?: string;
  range?: string;
  tone?: Tone;
  info?: string;
}

export function KpiCard({ label, value, hint, range, tone = "neutral", info }: Props) {
  return (
    <div className={`kpi kpi--${tone}`}>
      <div className="kpi-label">
        {label}
        {info ? (
          <span className="info" tabIndex={0} role="note" aria-label={info} title={info}>
            i
          </span>
        ) : null}
      </div>
      <div className="kpi-value">{value}</div>
      {hint ? <div className="kpi-hint">{hint}</div> : null}
      {range ? <div className="kpi-range">{range}</div> : null}
    </div>
  );
}