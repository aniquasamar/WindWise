import assert from "node:assert/strict";
import { test } from "node:test";
import { toCsv } from "../src/lib/csv";

test("csv quotes only where needed and leaves nulls empty", () => {
  assert.equal(toCsv([["Hour", "Forecast"], ["00:00", 1234.5], ["a,b", null], ['say "hi"', "x"]]),
    'Hour,Forecast\r\n00:00,1234.5\r\n"a,b",\r\n"say ""hi""",x\r\n');
});