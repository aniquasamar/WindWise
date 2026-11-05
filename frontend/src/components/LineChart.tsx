import { useRef, useState } from "react";
import { gapPolygons, linePath, nearestIndex } from "../lib/chart";
import { linear, niceTicks } from "../lib/scale";
import { useElementWidth } from "../lib/useElementWidth";
import { ChartTooltip } from "./chartParts";
import type { TooltipRow } from "./chartParts";

export interface ChartSeries {
  id: string;
  label: string;
  color: string;                         // any CSS colour, normally a theme variable such as "var(--forecast)"
  values: Array<number | null>;
  line?: "solid" | "dashed" | "dotted";
  width?: number;
}

export interface ChartGap {
  a: string;                             // id of the first series
  b: string;                             // id of the second series
  aboveColor: string;                    // fill where a is above b
  belowColor: string;                    // fill where a is below b
}

interface Props {
  xLabels: string[];
  series: ChartSeries[];
  ariaLabel: string;
  yFormat: (value: number) => string;
  title: (index: number) => string;
  extraRows?: (index: number) => TooltipRow[];
  gap?: ChartGap;
  height?: number;
}

const DASH: Record<string, string | undefined> = { solid: undefined, dashed: "7 5", dotted: "1.5 4.5" };
const MARGIN = { top: 14, right: 18, bottom: 30, left: 64 };

export function LineChart({ xLabels, series, ariaLabel, yFormat, title, extraRows, gap, height = 340 }: Props) {
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const width = useElementWidth(wrapRef);
  const [active, setActive] = useState<number | null>(null);

  const n = xLabels.length;
  const h = width < 520 ? Math.min(height, 280) : height;
  const plotW = width - MARGIN.left - MARGIN.right;
  const step = n > 1 ? plotW / (n - 1) : 0;
  const xOf = (i: number) => MARGIN.left + i * step;
  const xs = xLabels.map((_, i) => xOf(i));

  const all = series.flatMap((s) => s.values).filter((v): v is number => v !== null);
  const ticks = niceTicks(0, (all.length ? Math.max(...all) : 1) * 1.04, 5);
  const yMax = ticks[ticks.length - 1];
  const y = linear(0, yMax, h - MARGIN.bottom, MARGIN.top);
  const tickEvery = width < 520 ? 6 : 3;

  const byId = (id: string) => series.find((s) => s.id === id);
  const sa = gap ? byId(gap.a) : undefined;
  const sb = gap ? byId(gap.b) : undefined;
  const polygons = gap && sa && sb ? gapPolygons(xs, sa.values, sb.values, y) : [];

  function hover(clientX: number) {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;
    setActive(nearestIndex(clientX - rect.left, MARGIN.left, step, n));
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

  const rows: TooltipRow[] =
    active === null
      ? []
      : [
          ...series
            .filter((s) => s.values[active] !== null && s.values[active] !== undefined)
            .map((s) => ({ label: s.label, value: yFormat(s.values[active] as number), color: s.color })),
          ...(extraRows ? extraRows(active) : []),
        ];

  return (
    <div
      ref={wrapRef}
      className="chart"
      tabIndex={0}
      role="group"
      aria-label={`${ariaLabel}. Use the left and right arrow keys to inspect each hour.`}
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
        {xLabels.map((label, i) =>
          i % tickEvery === 0 ? (
            <text key={label} x={xOf(i)} y={h - 9} textAnchor="middle" className="tick-label">
              {label}
            </text>
          ) : null,
        )}

        {gap
          ? polygons.map((p, i) => (
              <polygon
                key={`gap-${i}`}
                points={p.points.map(([px, py]) => `${px.toFixed(1)},${py.toFixed(1)}`).join(" ")}
                style={{ fill: p.firstAbove ? gap.aboveColor : gap.belowColor }}
                className="gap-fill"
              />
            ))
          : null}

        {series.map((s) => (
          <path
            key={s.id}
            d={linePath(xs, s.values.map((v) => (v === null ? null : y(v))))}
            fill="none"
            strokeLinejoin="round"
            strokeLinecap="round"
            strokeWidth={s.width ?? 2.4}
            strokeDasharray={DASH[s.line ?? "solid"]}
            style={{ stroke: s.color }}
          />
        ))}

        {active !== null ? (
          <g>
            <line x1={xOf(active)} x2={xOf(active)} y1={MARGIN.top} y2={h - MARGIN.bottom} className="crosshair" />
            {series.map((s) => {
              const v = s.values[active];
              return v === null || v === undefined ? null : (
                <circle key={s.id} cx={xOf(active)} cy={y(v)} r={4.5} className="dot" style={{ stroke: s.color }} />
              );
            })}
          </g>
        ) : null}

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

      {active !== null ? <ChartTooltip x={xOf(active)} width={width} title={title(active)} rows={rows} /> : null}
      <div className="sr-only" aria-live="polite">
        {active !== null ? `${title(active)}. ${rows.map((r) => `${r.label} ${r.value}`).join(". ")}` : ""}
      </div>
    </div>
  );
}