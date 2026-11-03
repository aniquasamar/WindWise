import assert from "node:assert/strict";
import { test } from "node:test";
import { THEME_KEY, readStoredTheme, resolveTheme, saveTheme } from "../src/lib/theme";

test("an explicit saved choice wins over the system setting", () => {
  assert.equal(resolveTheme("light", true), "light");
  assert.equal(resolveTheme("dark", false), "dark");
});

test("without a saved choice the system setting decides", () => {
  assert.equal(resolveTheme(null, true), "dark");
  assert.equal(resolveTheme(null, false), "light");
  assert.equal(resolveTheme("blue", false), "light");     // garbage is ignored
});

test("blocked storage never throws", () => {
  const blocked = { getItem() { throw new Error("denied"); }, setItem() { throw new Error("denied"); } };
  assert.equal(readStoredTheme(blocked), null);
  assert.doesNotThrow(() => saveTheme(blocked, "dark"));
  assert.equal(readStoredTheme(undefined), null);
});

test("round trip", () => {
  const data = new Map<string, string>();
  const store = { getItem: (k: string) => data.get(k) ?? null, setItem: (k: string, v: string) => void data.set(k, v) };
  saveTheme(store, "dark");
  assert.equal(readStoredTheme(store), "dark");
  assert.equal(data.get(THEME_KEY), "dark");
});