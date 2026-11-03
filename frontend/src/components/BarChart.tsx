import { useRef, useState } from "react";
import { bandIndex, barRect, valueDomain } from "../lib/bars";
import { linePath } from "../lib/chart";
import { linear } from "../lib/scale";
import { ChartTooltip, useElementWidth } from "./chartParts";
import type { TooltipRow } from "./chartParts";

export interface Bar {
  label: string;
  value: number | null;
  color?: string;
}

/** A second measure drawn as dots (optionally joined by a line) on the same axis as the bars. */
export interface Overlay {
  color: string;
  values: Array<number | null>;
  connect?: boolean;
}

export interface RefLine {
  value: number;
  label: string;
  color?: string;
}

/** A vertical marker at a fractional bar position (0 is the left edge of the first bar). */
export interface VMarker {
  position: number;
  label: string;
  color?: string;
}

interface Props {
  bars: Bar[];
  overlay?: Overlay;
  refLines?: RefLine[];
  vMarkers?: VMarker[];
  ariaLabel: string;
  yFormat: (value: number) => string;
  valueLabel?: (value: number) => string;
  title: (index: number) => string;
  rows: (index: number) => TooltipRow[];
  height?: number;
  gap?: number;
  xTickEvery?: number;
  xTickLabel?: (index: number) => string;
  /** Cap the value axis (for example 100 for percentages). */
  domainMax?: number;
}

const MARGIN = { top: 18, right: 16, bottom: 32, left: 64 };

export function BarChart({
  bars, overlay, refLines = [], vMarkers = [], ariaLabel, yFormat, valueLabel, title, rows,
  height = 300, gap = 0.28, xTickEvery = 1, xTickLabel, domainMax,
}: Props) {
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const width = useElementWidth(wrapRef);
  const [active, setActive] = useState<number | null>(null);

  const n = bars.length;
  const h = width < 520 ? Math.min(height, 260) : height;
  const plotW = width - MARGIN.left - MARGIN.right;
  const band = n > 0 ? plotW / n : plotW;
  const extras = [...(overlay ? overlay.values.filter((v): v is number => v !== null) : []), ...refLines.map((r) => r.value)];
  const domain = valueDomain(bars.map((b) => b.value), extras);
  const ticks = domainMax === undefined ? domain.ticks : domain.ticks.filter((t) => t <= domainMax);
  const y = linear(domain.min, domainMax ?? domain.max, h - MARGIN.bottom, MARGIN.top);
  const xCenter = (i: number) => MARGIN.left + band * (i + 0.5);
  const every = n > 8 && width < 520 ? xTickEvery * 2 : xTickEvery;
  const showValues = valueLabel !== undefined && n <= 12;
  const rects = bars.map((b, i) => (b.value === null ? null : barRect(i, b.value, MARGIN.left, band, gap, y)));

  function hover(clientX: number) {
    const rect = svgRef.current?.getBoundingClientRect();
    if (rect) setActive(bandIndex(clientX - rect.left, MARGIN.left, band, n));
  }

  function handleKey(key: string): boolean {
    if (key === "ArrowRight") setActive((a) => (a === null ? 0 : Math.min(n - 1, a + 1)));
    else if (key === "ArrowLeft") setActive((a) => (a === null ? n - 1 : Math.max(0, a - 1)));
    else if (key === "Home") setActive(0);
    else if (key === "End") setActive(n - 1);
    else if (key === "Escape") setActive(null);
    else return false;
    return true;
  }

  const tooltipRows = active === null ? [] : rows(active);

  return (
    <div
      ref={wrapRef}
      className="chart"
      tabIndex={0}
      role="group"
      aria-label={`${ariaLabel}. Use the left and right arrow keys to inspect each bar.`}
      onKeyDown={(e) => {
        if (handleKey(e.key)) e.preventDefault();
      }}
      onFocus={() => setActive((a) => a ?? 0)}
      onBlur={() => setActive(null)}
    >
      <svg ref={svgRef} width={width} height={h} role="img" aria-label={ariaLabel} className="chart-svg">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={MARGIN.left} x2={width - MARGIN.right} y1={y(t)} y2={y(t)} className={t === 0 ? "axis-line" : "grid-line"} />
            <text x={MARGIN.left - 10} y={y(t)} dy="0.32em" textAnchor="end" className="tick-label">
              {yFormat(t)}
            </text>
          </g>
        ))}

        {active !== null ? <rect x={MARGIN.left + band * active} y={MARGIN.top} width={band} height={h - MARGIN.top - MARGIN.bottom} className="band-highlight" /> : null}

        {bars.map((b, i) => {
          const r = rects[i];
          if (b.value === null || r === null) return null;
          return <rect key={`${b.label}-${i}`} x={r.x} y={r.y} width={r.width} height={r.height} rx={Math.min(3, r.width / 4)} style={{ fill: b.color ?? "var(--forecast)" }} />;
        })}

        {showValues
          ? bars.map((b, i) => {
              const r = rects[i];
              if (b.value === null || r === null) return null;
              // Tall bars carry their label inside, in a contrasting colour, so overlay dots never collide with it.
              const inside = r.height >= 28;
              const positive = b.value >= 0;
              const ty = inside ? (positive ? r.y + 18 : r.y + r.height - 8) : positive ? r.y - 7 : r.y + r.height + 16;
              return (
                <text key={`v-${i}`} x={xCenter(i)} y={ty} textAnchor="middle" className={inside ? "value-label value-label--inside" : "value-label"}>
                  {valueLabel(b.value)}
                </text>
              );
            })
          : null}

        {refLines.map((r) => (
          <g key={r.label}>
            <line x1={MARGIN.left} x2={width - MARGIN.right} y1={y(r.value)} y2={y(r.value)} className="ref-line" style={{ stroke: r.color ?? "var(--muted)" }} />
            <text x={width - MARGIN.right - 4} y={y(r.value) - 6} textAnchor="end" className="ref-label" style={{ fill: r.color ?? "var(--muted)" }}>
              {r.label}
            </text>
          </g>
        ))}

        {vMarkers.map((m) => {
          const x = MARGIN.left + band * m.position;
          const flip = x > width * 0.7;
          return (
            <g key={m.label}>
              <line x1={x} x2={x} y1={MARGIN.top} y2={h - MARGIN.bottom} className="vmarker" style={{ stroke: m.color ?? "var(--text)" }} />
              <text x={flip ? x - 5 : x + 5} y={MARGIN.top + 11} textAnchor={flip ? "end" : "start"} className="ref-label" style={{ fill: m.color ?? "var(--text)" }}>
                {m.label}
              </text>
            </g>
          );
        })}

        {overlay ? (
          <g>
            {overlay.connect !== false ? (
              <path
                d={linePath(bars.map((_, i) => xCenter(i)), overlay.values.map((v) => (v === null ? null : y(v))))}
                fill="none"
                strokeWidth={2.2}
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{ stroke: overlay.color }}
                strokeDasharray="1.5 4.5"
              />
            ) : null}
            {overlay.values.map((v, i) =>
              v === null ? null : <circle key={`o-${i}`} cx={xCenter(i)} cy={y(v)} r={4} className="dot" style={{ stroke: overlay.color }} />,
            )}
          </g>
        ) : null}

        {bars.map((b, i) =>
          i % every === 0 ? (
            <text key={`x-${i}`} x={xCenter(i)} y={h - 10} textAnchor="middle" className="tick-label">
              {xTickLabel ? xTickLabel(i) : b.label}
            </text>
          ) : null,
        )}

        <rect
          x={MARGIN.left}
          y={MARGIN.top}
          width={plotW}
          height={h - MARGIN.top - MARGIN.bottom}
          fill="transparent"
          style={{ touchAction: "pan-y" }}
          onPointerMove={(e) => hover(e.clientX)}
          onPointerDown={(e) => hover(e.clientX)}
          onPointerLeave={() => setActive(null)}
        />
      </svg>

      {active !== null ? <ChartTooltip x={xCenter(active)} width={width} title={title(active)} rows={tooltipRows} /> : null}
      <div className="sr-only" aria-live="polite">
        {active !== null ? `${title(active)}. ${tooltipRows.map((r) => `${r.label} ${r.value}`).join(". ")}` : ""}
      </div>
    </div>
  );
}