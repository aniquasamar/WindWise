import assert from "node:assert/strict";
import { test } from "node:test";
import { fmtClock, fmtDateLong, fmtDateShort, fmtDuration, fmtInstantDay, fmtMw, fmtNumber, fmtOdds, fmtPct, plural } from "../src/lib/format";

test("numbers use thousands separators and a true minus sign", () => {
  assert.equal(fmtNumber(1748.4), "1,748");
  assert.equal(fmtNumber(-1748.6), "\u22121,749");
  assert.equal(fmtNumber(1748, true), "+1,748");
  assert.equal(fmtNumber(0, true), "0");
  assert.equal(fmtNumber(-0.2, true), "0");          // rounds to zero: no sign
  assert.equal(fmtNumber(null), "\u2013");
  assert.equal(fmtNumber(Number.NaN), "\u2013");
});

test("megawatts", () => {
  assert.equal(fmtMw(4098), "4,098 MW");
  assert.equal(fmtMw(-549, true), "\u2212549 MW");
  assert.equal(fmtMw(null), "\u2013");
});

test("percentages", () => {
  assert.equal(fmtPct(0.855, 1), "85.5%");
  assert.equal(fmtPct(0.849), "85%");
  assert.equal(fmtPct(0.15, 0, true), "+15%");
  assert.equal(fmtPct(-0.2, 0, true), "\u221220%");
  assert.equal(fmtPct(null), "\u2013");
});

test("dates are formatted without locale or timezone drift", () => {
  assert.equal(fmtDateLong("2026-01-28"), "Wed 28 Jan 2026");
  assert.equal(fmtDateLong("2026-02-01"), "Sun 1 Feb 2026");
  assert.equal(fmtDateShort("2026-01-02"), "2 Jan");
});

test("clock times use UK time", () => {
  assert.equal(fmtClock("2026-01-27T07:30:00Z"), "07:30");
  assert.equal(fmtClock("2026-01-27T00:00:00Z"), "00:00");
  assert.equal(fmtClock("2026-07-14T07:30:00Z"), "08:30");     // summer: UK is one hour ahead of UTC
  assert.equal(fmtInstantDay("2026-01-27T07:30:00Z"), "27 Jan");
});

test("durations", () => {
  assert.equal(fmtDuration(1.5), "1 h 30 min");
  assert.equal(fmtDuration(0.75), "45 min");
  assert.equal(fmtDuration(2), "2 h");
});

test("plural", () => {
  assert.equal(plural(1, "day", "days"), "day");
  assert.equal(plural(5, "day", "days"), "days");
});

test("odds phrases", () => {
  assert.equal(fmtOdds(0.9), "9 times out of 10");
  assert.equal(fmtOdds(0.8), "4 times out of 5");
  assert.equal(fmtOdds(0.95), "19 times out of 20");
  assert.equal(fmtOdds(0.7), "70%");
});