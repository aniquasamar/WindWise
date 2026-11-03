// Geometry helpers for the SVG line chart (pure, so they can be tested without a browser).

export type Maybe = number | null;

/** SVG path through the points, with a break wherever a value is missing. */
export function linePath(xs: number[], ys: Maybe[]): string {
  let d = "";
  let pen = false;
  for (let i = 0; i < xs.length; i++) {
    const y = ys[i];
    if (y === null || y === undefined || Number.isNaN(y)) {
      pen = false;
      continue;
    }
    d += `${pen ? "L" : "M"}${xs[i].toFixed(1)} ${y.toFixed(1)}`;
    pen = true;
  }
  return d;
}

export interface GapPolygon {
  points: Array<[number, number]>;
  /** True where the first series is above the second. */
  firstAbove: boolean;
}

/**
 * Polygons that fill the area between two series, split where the lines cross, so the gap can be
 * shaded by direction (forecast above actual vs below). `y` maps a value to a pixel row.
 */
export function gapPolygons(xs: number[], a: Maybe[], b: Maybe[], y: (v: number) => number): GapPolygon[] {
  const out: GapPolygon[] = [];
  for (let i = 0; i + 1 < xs.length; i++) {
    const a0 = a[i], a1 = a[i + 1], b0 = b[i], b1 = b[i + 1];
    if (a0 === null || a1 === null || b0 === null || b1 === null) continue;
    if (a0 === undefined || a1 === undefined || b0 === undefined || b1 === undefined) continue;
    const d0 = a0 - b0;
    const d1 = a1 - b1;
    const x0 = xs[i], x1 = xs[i + 1];
    if (d0 * d1 >= 0) {
      const firstAbove = d0 > 0 || (d0 === 0 && d1 > 0);
      if (d0 === 0 && d1 === 0) continue;
      out.push({ points: [[x0, y(a0)], [x1, y(a1)], [x1, y(b1)], [x0, y(b0)]], firstAbove });
    } else {
      const t = d0 / (d0 - d1);
      const xc = x0 + t * (x1 - x0);
      const vc = a0 + t * (a1 - a0);
      out.push({ points: [[x0, y(a0)], [xc, y(vc)], [x0, y(b0)]], firstAbove: d0 > 0 });
      out.push({ points: [[xc, y(vc)], [x1, y(a1)], [x1, y(b1)]], firstAbove: d1 > 0 });
    }
  }
  return out;
}

/** Index of the data point nearest to a pixel position. */
export function nearestIndex(px: number, left: number, step: number, count: number): number {
  if (count <= 1 || step <= 0) return 0;
  return Math.max(0, Math.min(count - 1, Math.round((px - left) / step)));
}