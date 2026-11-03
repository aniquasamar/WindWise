import { useEffect, useState } from "react";

export interface TooltipRow {
  label: string;
  value: string;
  color?: string;
}

/** Width of an element, kept up to date as it resizes. The first measurement arrives with the observer. */
export function useElementWidth(ref: { current: HTMLDivElement | null }, fallback = 720): number {
  const [width, setWidth] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new ResizeObserver(() => setWidth(Math.max(280, Math.floor(el.clientWidth))));
    observer.observe(el);
    return () => observer.disconnect();
  }, [ref]);
  return width;
}

interface TooltipProps {
  x: number;
  width: number;
  title: string;
  rows: TooltipRow[];
}

export function ChartTooltip({ x, width, title, rows }: TooltipProps) {
  const onRight = x > width * 0.62;
  return (
    <div className="tooltip" style={onRight ? { right: width - x + 14, top: 10 } : { left: x + 14, top: 10 }}>
      <div className="tooltip-title">{title}</div>
      {rows.map((r) => (
        <div key={r.label} className="tooltip-row">
          <span className="tooltip-label">
            {r.color ? <i className="tooltip-swatch" style={{ background: r.color }} /> : null}
            {r.label}
          </span>
          <span className="tooltip-value">{r.value}</span>
        </div>
      ))}
    </div>
  );
}