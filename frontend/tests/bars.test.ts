import assert from "node:assert/strict";
import { test } from "node:test";
import { bandIndex, barRect, valueDomain } from "../src/lib/bars";
import { linear } from "../src/lib/scale";

test("the axis always includes zero", () => {
  const all = valueDomain([1200, 3400]);
  assert.equal(all.min, 0);
  assert.ok(all.max >= 3400);
  const negative = valueDomain([-500, -200]);
  assert.equal(negative.max, 0);
  assert.ok(negative.min <= -500);
  const mixed = valueDomain([-549, 4098]);
  assert.ok(mixed.min <= -549 && mixed.max >= 4098 && mixed.ticks.includes(0));
});

test("extra values (overlay markers, reference lines) stretch the axis too", () => {
  assert.ok(valueDomain([10, 20], [95]).max >= 95);
});

test("an empty or all-zero chart still gets a usable axis", () => {
  const d = valueDomain([null, null]);
  assert.ok(d.ticks.length >= 2 && d.min <= 0 && d.max >= 0);
  assert.ok(valueDomain([0, 0]).ticks.length >= 2);
});

test("positive bars rise from zero, negative bars hang below it", () => {
  const y = linear(-100, 100, 200, 0);              // zero sits at pixel row 100
  const up = barRect(0, 50, 10, 20, 0.2, y);
  const down = barRect(1, -50, 10, 20, 0.2, y);
  assert.equal(up.y, 50);
  assert.equal(up.height, 50);
  assert.equal(down.y, 100);
  assert.equal(down.height, 50);
  assert.equal(up.width, 16);                       // 20 * (1 - 0.2)
  assert.equal(up.x, 12);                           // centred in its band
  assert.equal(down.x, 32);
});

test("tiny bars stay visible and zero bars have no height", () => {
  const y = linear(0, 1000, 100, 0);
  assert.equal(barRect(0, 1, 0, 10, 0, y).height, 1);
  assert.equal(barRect(0, 0, 0, 10, 0, y).height, 0);
});

test("bandIndex picks the bar under the pointer and clamps to the edges", () => {
  assert.equal(bandIndex(15, 10, 10, 5), 0);
  assert.equal(bandIndex(25, 10, 10, 5), 1);
  assert.equal(bandIndex(-50, 10, 10, 5), 0);
  assert.equal(bandIndex(500, 10, 10, 5), 4);
  assert.equal(bandIndex(15, 10, 10, 0), 0);
});