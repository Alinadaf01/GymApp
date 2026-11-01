import { test } from "node:test";
import assert from "node:assert/strict";
import { niceTicks } from "../lib/chart-scale.ts";

test("ticks cover the data range with round steps", () => {
  for (const [min, max] of [[82.4, 88], [30, 31], [0.5, 120], [70, 70]]) {
    const t = niceTicks(min, max);
    assert.ok(t[0] <= min && t[t.length - 1] >= max, `${min}-${max}: ${t}`);
    const steps = new Set(t.slice(1).map((v, i) => Number((v - t[i]).toFixed(6))));
    assert.equal(steps.size, 1, `even steps ${t}`);
    assert.ok(t.length >= 2 && t.length <= 7, `count ${t}`);
  }
  assert.deepEqual(niceTicks(82.4, 88), [82, 84, 86, 88]);
  assert.deepEqual(niceTicks(0.5, 120), [0, 50, 100, 150]); // top tick reaches the max
});
