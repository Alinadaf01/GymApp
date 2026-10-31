// End-to-end smoke test for auth + panel shell + dashboard.
// Requires running API + web, and a coach account:
//   E2E_USERNAME=coach E2E_PASSWORD=... node e2e/phase2.smoke.mjs
// Uses the preinstalled Playwright (require('playwright')).
import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const USER = process.env.E2E_USERNAME;
const PASS = process.env.E2E_PASSWORD;
const SHOTS = process.env.E2E_SCREENSHOTS; // optional output dir
assert.ok(USER && PASS, "set E2E_USERNAME and E2E_PASSWORD");

const browser = await chromium.launch();
const step = (name) => console.log(`✓ ${name}`);

try {
  // --- desktop ---
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 860 } });
  const page = await ctx.newPage();

  await page.goto(`${BASE}/dashboard`);
  await page.waitForURL(/\/login\?next=%2Fdashboard/);
  step("unauthenticated user is redirected to login");
  assert.equal(await page.evaluate(() => document.documentElement.dir), "rtl");

  await page.fill("#username", USER);
  await page.fill("#password", "wrong-password");
  await page.click("button[type=submit]");
  await page.getByText("نام کاربری یا رمز عبور اشتباه است.").waitFor();
  step("wrong password shows Persian error");

  await page.fill("#password", PASS);
  await page.click("button[type=submit]");
  await page.waitForURL(/\/dashboard$/);
  await page.getByRole("heading", { name: "داشبورد" }).waitFor();
  await page.getByText("کل شاگردان").waitFor();
  await page.waitForFunction(() => !document.querySelector('[data-slot="skeleton"]'));
  step("login succeeds and dashboard renders");

  const cookies = await ctx.cookies();
  const session = cookies.find((c) => c.name.endsWith("basharnia_session"));
  assert.ok(session?.httpOnly, "session cookie must be HttpOnly");
  assert.equal(await page.evaluate(() => document.cookie.includes("basharnia_session")), false);
  assert.equal(await page.evaluate(() => Object.keys(localStorage).length), 0);
  step("session cookie is HttpOnly and nothing is stored in localStorage");

  if (SHOTS) await page.screenshot({ path: `${SHOTS}/dashboard-desktop.png`, fullPage: true });

  await page.getByRole("link", { name: "تنظیمات" }).click();
  await page.waitForURL(/\/settings$/);
  await page.getByText("تغییر رمز عبور").first().waitFor();
  await page.fill("#current", PASS);
  await page.fill("#next", "short");
  await page.fill("#confirm", "short");
  await page.getByRole("button", { name: "ذخیره رمز جدید" }).click();
  await page.getByText("رمز جدید باید حداقل").waitFor();
  step("settings: change-password validation");

  await page.getByRole("button", { name: "خروج" }).click();
  await page.waitForURL(/\/login/);
  await page.goto(`${BASE}/dashboard`);
  await page.waitForURL(/\/login/);
  step("logout ends the session");
  await ctx.close();

  // --- mobile ---
  const m = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true });
  const mp = await m.newPage();
  await mp.goto(`${BASE}/login`);
  await mp.fill("#username", USER);
  await mp.fill("#password", PASS);
  await mp.click("button[type=submit]");
  await mp.waitForURL(/\/dashboard$/);
  await mp.waitForFunction(() => !document.querySelector('[data-slot="skeleton"]'));
  assert.ok(await mp.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), "no horizontal scroll");
  if (SHOTS) await mp.screenshot({ path: `${SHOTS}/dashboard-mobile.png`, fullPage: true });
  await mp.getByRole("button", { name: "باز کردن منو" }).click();
  await mp.getByRole("dialog").waitFor();
  await mp.waitForTimeout(400); // let the slide-in animation finish
  if (SHOTS) await mp.screenshot({ path: `${SHOTS}/menu-mobile.png` });
  await mp.getByRole("dialog").getByRole("link", { name: "شاگردان" }).click();
  await mp.waitForURL(/\/students$/);
  step("mobile: no horizontal scroll, sheet menu navigates");
  await m.close();

  console.log("ALL PASSED");
} finally {
  await browser.close();
}
