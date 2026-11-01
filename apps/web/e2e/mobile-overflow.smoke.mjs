// Every panel page at phone width must fit the screen (no horizontal page scroll),
// load without CSP violations or console errors.
//   E2E_USERNAME=coach E2E_PASSWORD=... node e2e/mobile-overflow.smoke.mjs
// Uses a plain 390px viewport (no mobile emulation: emulation widens the layout
// viewport to fit overflowing content, which hides the bug).
import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
// Self-signed test certificates (e.g. infra/tests/test-compose-stack.sh)
const IGNORE_TLS = !!process.env.E2E_IGNORE_HTTPS_ERRORS;
const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const API = process.env.E2E_API_URL ?? "http://localhost:8000";
const WIDTH = 390;

const browser = await chromium.launch();
try {
  const page = await (await browser.newContext({ ignoreHTTPSErrors: IGNORE_TLS, viewport: { width: WIDTH, height: 844 } })).newPage();
  // Also: no Content-Security-Policy violations or console errors on any page
  const consoleProblems = [];
  page.on("console", (m) => {
    if (m.type() === "error" || /Content Security Policy/i.test(m.text())) consoleProblems.push(`${page.url()}: ${m.text()}`);
  });
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
  assert.deepEqual(consoleProblems, [], consoleProblems.join("\n"));
  console.log("✓ no CSP violations or console errors");
  console.log("ALL PASSED");
} finally {
  await browser.close();
}
