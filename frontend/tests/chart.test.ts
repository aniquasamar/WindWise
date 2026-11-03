import assert from "node:assert/strict";
import { test } from "node:test";
import { gapPolygons, linePath, nearestIndex } from "../src/lib/chart";

const yPx = (v: number) => 100 - v;

test("linePath draws through points and breaks at missing values", () => {
  assert.equal(linePath([0, 10, 20], [1, 2, 3]), "M0.0 1.0L10.0 2.0L20.0 3.0");
  assert.equal(linePath([0, 10, 20, 30], [1, null, 3, 4]), "M0.0 1.0M20.0 3.0L30.0 4.0");
  assert.equal(linePath([0, 10], [null, null]), "");
});

test("gap polygon between two non-crossing lines", () => {
  const polys = gapPolygons([0, 10], [50, 60], [30, 40], yPx);
  assert.equal(polys.length, 1);
  assert.equal(polys[0].firstAbove, true);
  assert.deepEqual(polys[0].points, [[0, 50], [10, 40], [10, 60], [0, 70]]);
});

test("gap is split at the crossing point and each part is tagged by direction", () => {
  const polys = gapPolygons([0, 10], [20, 40], [40, 20], yPx);
  assert.equal(polys.length, 2);
  assert.equal(polys[0].firstAbove, false);
  assert.equal(polys[1].firstAbove, true);
  assert.deepEqual(polys[0].points[1], [5, 70]);           // lines cross halfway, at value 30
  assert.deepEqual(polys[1].points[0], [5, 70]);
});

test("segments with a missing value or no gap produce nothing", () => {
  assert.deepEqual(gapPolygons([0, 10], [20, null], [40, 20], yPx), []);
  assert.deepEqual(gapPolygons([0, 10], [20, 30], [20, 30], yPx), []);
});

test("nearestIndex snaps to the closest point and stays in range", () => {
  assert.equal(nearestIndex(100, 50, 10, 24), 5);
  assert.equal(nearestIndex(0, 50, 10, 24), 0);
  assert.equal(nearestIndex(5000, 50, 10, 24), 23);
  assert.equal(nearestIndex(100, 50, 10, 1), 0);
});