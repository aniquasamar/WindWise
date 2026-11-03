// Geometry for the bar chart (pure, so it can be tested without a browser).
import { niceTicks } from "./scale";

export interface Domain {
  ticks: number[];
  min: number;
  max: number;
}

/** Axis range for bars: always includes zero, with a little headroom, rounded to nice tick values. */
export function valueDomain(values: Array<number | null>, extras: number[] = []): Domain {
  const all = [...values.filter((v): v is number => v !== null && !Number.isNaN(v)), ...extras, 0];
  const lo = Math.min(...all);
  const hi = Math.max(...all);
  const pad = (hi - lo) * 0.06 || 1;
  const ticks = niceTicks(lo < 0 ? lo - pad : 0, hi > 0 ? hi + pad : 0, 5);
  return { ticks, min: ticks[0], max: ticks[ticks.length - 1] };
}

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** Rectangle of bar `index`. Bars grow up from zero for positive values and down for negative ones. */
export function barRect(index: number, value: number, left: number, band: number, gap: number, yOf: (v: number) => number): Rect {
  const width = band * (1 - gap);
  const x = left + band * index + (band - width) / 2;
  const zero = yOf(0);
  const top = yOf(value);
  return { x, y: Math.min(zero, top), width, height: value === 0 ? 0 : Math.max(Math.abs(top - zero), 1) };
}

/** Index of the bar whose band contains a pixel position, kept within range. */
export function bandIndex(px: number, left: number, band: number, count: number): number {
  if (count <= 0 || band <= 0) return 0;
  return Math.max(0, Math.min(count - 1, Math.floor((px - left) / band)));
}