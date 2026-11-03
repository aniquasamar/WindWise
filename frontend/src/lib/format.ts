// Display formatting. Deterministic (no locale surprises) and typographically careful:
// a true minus sign for negatives, thousands separators, tabular-friendly output.

const MINUS = "\u2212";
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const intFormat = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 0 });

function sign(value: number, signed: boolean): string {
  if (value < 0) return MINUS;
  return signed && value > 0 ? "+" : "";
}

export function fmtNumber(x: number | null | undefined, signed = false): string {
  if (x === null || x === undefined || Number.isNaN(x)) return "\u2013";
  const rounded = Math.round(x);
  return sign(rounded, signed) + intFormat.format(Math.abs(rounded));
}

export function fmtMw(x: number | null | undefined, signed = false): string {
  return x === null || x === undefined ? "\u2013" : `${fmtNumber(x, signed)} MW`;
}

export function fmtPct(x: number | null | undefined, digits = 0, signed = false): string {
  if (x === null || x === undefined || Number.isNaN(x)) return "\u2013";
  const value = Number((x * 100).toFixed(digits));
  return `${sign(value, signed)}${Math.abs(value).toFixed(digits)}%`;
}

function parseIsoDate(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d));
}

/** "Wed 28 Jan 2026" from "2026-01-28". */
export function fmtDateLong(iso: string): string {
  const d = parseIsoDate(iso);
  return `${WEEKDAYS[d.getUTCDay()]} ${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}

/** "28 Jan" from "2026-01-28". */
export function fmtDateShort(iso: string): string {
  const d = parseIsoDate(iso);
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;
}

const clockFormat = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Europe/London",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});
const dayFormat = new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/London", day: "numeric", month: "short" });

/** UK clock time ("07:30") of an ISO 8601 instant. */
export function fmtClock(isoInstant: string): string {
  return clockFormat.format(new Date(isoInstant));
}

/** UK date ("27 Jan") of an ISO 8601 instant. */
export function fmtInstantDay(isoInstant: string): string {
  return dayFormat.format(new Date(isoInstant));
}

/** 1.5 -> "1 h 30 min", 0.75 -> "45 min", 2 -> "2 h". */
export function fmtDuration(hours: number): string {
  const total = Math.round(hours * 60);
  const h = Math.floor(total / 60);
  const m = total % 60;
  if (h === 0) return `${m} min`;
  return m === 0 ? `${h} h` : `${h} h ${m} min`;
}

export function plural(n: number, one: string, many: string): string {
  return n === 1 ? one : many;
}

/** 0.9 -> "9 times out of 10". Falls back to a percentage for other levels. */
export function fmtOdds(confidence: number): string {
  const known: Record<string, string> = { "0.8": "4 times out of 5", "0.9": "9 times out of 10", "0.95": "19 times out of 20" };
  return known[String(confidence)] ?? fmtPct(confidence);
}