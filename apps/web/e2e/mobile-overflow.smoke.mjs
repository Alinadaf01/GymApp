// Every panel page at phone width must fit the screen (no horizontal page scroll).
//   E2E_USERNAME=coach E2E_PASSWORD=... node e2e/mobile-overflow.smoke.mjs
// Uses a plain 390px viewport (no mobile emulation: emulation widens the layout
// viewport to fit overflowing content, which hides the bug).
import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const API = process.env.E2E_API_URL ?? "http://localhost:8000";
const WIDTH = 390;

const browser = await chromium.launch();
try {
  const page = await (await browser.newContext({ viewport: { width: WIDTH, height: 844 } })).newPage();
  await page.goto(`${BASE}/login`);
  await page.fill("#username", process.env.E2E_USERNAME);
  await page.fill("#password", process.env.E2E_PASSWORD);
  await page.click("button[type=submit]");
  await page.waitForURL(/\/dashboard$/);

  // pick existing records to visit (whatever the dev DB contains)
  const ids = await page.evaluate(async (api) => {
    const get = (u) => fetch(api + u, { credentials: "include" }).then((r) => r.json());
    const students = (await get("/api/students?status=all&page_size=5")).items;
    const programs = (await get("/api/programs?status=all&page_size=5")).items;
    return { students: students.map((s) => s.id), programs: programs.map((p) => p.id) };
  }, API);
  const routes = ["/dashboard", "/students", "/students/new", "/programs", "/programs/new", "/settings",
    "/settings/dictionary"];
  for (const id of ids.students.slice(0, 3)) {
    for (const tab of ["", "?tab=programs", "?tab=photos", "?tab=trends", "?tab=history"]) routes.push(`/students/${id}${tab}`);
    routes.push(`/students/${id}/edit`);
  }
  for (const id of ids.programs.slice(0, 3)) routes.push(`/programs/${id}`, `/programs/${id}/edit`);

  const failures = [];
  for (const route of routes) {
    await page.goto(`${BASE}${route}`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(250);
    const sw = await page.evaluate(() => document.documentElement.scrollWidth);
    if (sw > WIDTH) failures.push(`${route}: page is ${sw}px wide`);
  }
  assert.deepEqual(failures, [], failures.join("\n"));
  console.log(`✓ ${routes.length} pages fit ${WIDTH}px`);
  console.log("ALL PASSED");
} finally {
  await browser.close();
}
