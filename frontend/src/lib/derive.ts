// Values derived from API data for display. Pure functions, unit-tested.
import type { DayOut, PointOut } from "../api/types";

export interface DayResult {
  scoredHours: number;
  meanError: number | null;
  meanActual: number | null;
  /** Hours in which actual wind was at least the "firm wind" level. Null if no buffer exists. */
  firmHeldHours: number | null;
  firmHours: number;
}

export function dayResult(points: PointOut[]): DayResult {
  const scored = points.filter((p) => p.actual_mw !== null && p.error_mw !== null);
  const meanError = scored.length ? scored.reduce((s, p) => s + (p.error_mw as number), 0) / scored.length : null;
  const meanActual = scored.length ? scored.reduce((s, p) => s + (p.actual_mw as number), 0) / scored.length : null;
  const withFirm = scored.filter((p) => p.firm_mw !== null);
  return {
    scoredHours: scored.length,
    meanError,
    meanActual,
    firmHeldHours: withFirm.length ? withFirm.filter((p) => (p.actual_mw as number) >= (p.firm_mw as number)).length : null,
    firmHours: withFirm.length,
  };
}

export function peakPoint(points: PointOut[]): PointOut | null {
  let best: PointOut | null = null;
  for (const p of points) if (best === null || p.forecast_mw > best.forecast_mw) best = p;
  return best;
}

/** Delivery date whose mean error is largest in size (either direction). */
export function largestMissDate(days: DayOut[]): string | null {
  let best: DayOut | null = null;
  for (const d of days) {
    if (d.metrics.bias === null) continue;
    if (best === null || Math.abs(d.metrics.bias) > Math.abs(best.metrics.bias as number)) best = d;
  }
  return best ? best.delivery_date : null;
}

export function isIsoDate(value: string | null | undefined): value is string {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(value));
}

export function clampDate(iso: string, min: string, max: string): string {
  return iso < min ? min : iso > max ? max : iso;
}

export function shiftDate(iso: string, days: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10);
}

/** "03:00", "03:15", ... "16:00" */
export function cutoffOptions(min: string, max: string, stepMinutes: number): string[] {
  const toMinutes = (t: string) => Number(t.slice(0, 2)) * 60 + Number(t.slice(3, 5));
  const out: string[] = [];
  for (let m = toMinutes(min); m <= toMinutes(max); m += stepMinutes) {
    out.push(`${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`);
  }
  return out;
}