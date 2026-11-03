import assert from "node:assert/strict";
import { test } from "node:test";
import { buildHash, parseHash, withParams } from "../src/lib/hash";

test("parseHash splits path and query", () => {
  const r = parseHash("#/forecast?date=2026-01-28&cutoff=09:00");
  assert.equal(r.path, "/forecast");
  assert.equal(r.params.get("date"), "2026-01-28");
  assert.equal(r.params.get("cutoff"), "09:00");
});

test("an empty hash goes to the default page", () => {
  assert.equal(parseHash("").path, "/forecast");
  assert.equal(parseHash("#").path, "/forecast");
  assert.equal(parseHash("#/").path, "/forecast");
  assert.equal(parseHash("#accuracy").path, "/accuracy");
});

test("buildHash skips empty values and keeps colons readable", () => {
  assert.equal(buildHash("/forecast", { date: "2026-01-28", cutoff: "09:00", x: null, y: "" }), "#/forecast?date=2026-01-28&cutoff=09:00");
  assert.equal(buildHash("/accuracy", {}), "#/accuracy");
});

test("withParams updates, adds and removes params", () => {
  const next = withParams("#/forecast?date=2026-01-28&cutoff=09:00", { cutoff: "08:00", confidence: "0.95", date: null });
  const r = parseHash(next);
  assert.equal(r.path, "/forecast");
  assert.equal(r.params.get("cutoff"), "08:00");
  assert.equal(r.params.get("confidence"), "0.95");
  assert.equal(r.params.has("date"), false);
});

test("hostile input stays inside the query string", () => {
  const r = parseHash("#/forecast?date=%3Cscript%3E&x=1");
  assert.equal(r.params.get("date"), "<script>");
  assert.equal(r.path, "/forecast");
});