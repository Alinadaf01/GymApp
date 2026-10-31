import { test } from "node:test";
import assert from "node:assert/strict";
import { safeNextPath } from "../lib/navigation.ts";

test("safeNextPath keeps internal paths", () => {
  assert.equal(safeNextPath("/students?q=1"), "/students?q=1");
});

test("safeNextPath blocks open redirects and loops", () => {
  for (const bad of [null, "", "https://evil.example", "//evil.example", "/\\evil.example", "/login", "dashboard"]) {
    assert.equal(safeNextPath(bad), "/dashboard");
  }
});
