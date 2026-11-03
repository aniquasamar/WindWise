import assert from "node:assert/strict";
import { test } from "node:test";
import { linear, niceTicks } from "../src/lib/scale";

test("ticks are round numbers covering the data", () => {
  const t = niceTicks(0, 19888);
  assert.equal(t[0], 0);
  assert.ok(t[t.length - 1] >= 19888);
  const step = t[1] - t[0];
  assert.ok([1, 2, 5].includes(Number((step / 10 ** Math.floor(Math.log10(step))).toFixed(6))));
  for (let i = 1; i < t.length; i++) assert.ok(Math.abs(t[i] - t[i - 1] - step) < 1e-6);
});

test("small and negative ranges", () => {
  assert.deepEqual(niceTicks(0, 1, 3), [0, 0.5, 1]);
  const t = niceTicks(-1200, 3400);
  assert.ok(t[0] <= -1200 && t[t.length - 1] >= 3400);
});

test("ticks stay tight around the data (no wasted axis)", () => {
  assert.deepEqual(niceTicks(0, 22508), [0, 5000, 10000, 15000, 20000, 25000]);
  assert.deepEqual(niceTicks(0, 19888), [0, 5000, 10000, 15000, 20000]);
  assert.deepEqual(niceTicks(0, 8200), [0, 2000, 4000, 6000, 8000, 10000]);
});

test("a flat range still gives usable ticks", () => {
  const t = niceTicks(5, 5);
  assert.ok(t.length >= 2 && t[0] < 5 && t[t.length - 1] > 5);
  assert.deepEqual(niceTicks(Number.NaN, 1), [0, 1]);
});

test("linear scale maps the domain to the range, including inverted ranges", () => {
  const y = linear(0, 100, 200, 0);
  assert.equal(y(0), 200);
  assert.equal(y(100), 0);
  assert.equal(y(50), 100);
  assert.equal(linear(5, 5, 0, 10)(5), 0);            // degenerate domain does not divide by zero
});