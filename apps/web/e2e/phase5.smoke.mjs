// E2E smoke test for the panel side of phase 5 (dictionary + programs from voice).
//   E2E_USERNAME=coach E2E_PASSWORD=... E2E_VOICE_STUDENT="تلگرام آزمایشی" node e2e/phase5.smoke.mjs
// Run apps/backend/scripts/e2e_telegram_flow.py first to create a program from a voice.
import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
// Self-signed test certificates (e.g. infra/tests/test-compose-stack.sh)
const IGNORE_TLS = !!process.env.E2E_IGNORE_HTTPS_ERRORS;

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const USER = process.env.E2E_USERNAME;
const PASS = process.env.E2E_PASSWORD;
const VOICE_STUDENT = process.env.E2E_VOICE_STUDENT;
const SHOTS = process.env.E2E_SCREENSHOTS;
assert.ok(USER && PASS, "set E2E_USERNAME and E2E_PASSWORD");

const step = (name) => console.log(`✓ ${name}`);
const vis = (locator) => locator.filter({ visible: true });
const uniq = Date.now().toString().slice(-5);

const browser = await chromium.launch();
try {
  const page = await (await browser.newContext({ ignoreHTTPSErrors: IGNORE_TLS, viewport: { width: 1280, height: 900 } })).newPage();
  await page.goto(`${BASE}/login`);
  await page.fill("#username", USER);
  await page.fill("#password", PASS);
  await page.click("button[type=submit]");
  await page.waitForURL(/\/dashboard$/);

  // --- dictionary ---
  await page.goto(`${BASE}/settings`);
  await vis(page.getByRole("link", { name: /فرهنگ لغت حرکات/ })).click();
  await page.waitForURL(/\/settings\/dictionary$/);
  await vis(page.getByText("پرس بالا سینه دمبل", { exact: true })).waitFor(); // seeded by migration
  const name = `پشت پا خوابیده ${uniq}`;
  await vis(page.locator("#new-name")).fill(name);
  await vis(page.locator("#new-aliases")).fill(`لگ کرل ${uniq}، پشت‌پا ${uniq}`);
  await vis(page.getByRole("button", { name: "افزودن" })).click();
  const row = vis(page.getByTestId("dictionary-entry")).filter({ hasText: name });
  await row.waitFor();
  await row.getByText(`لگ کرل ${uniq}`).waitFor();
  step("dictionary: seeded entries listed, new entry with aliases added");

  // the same spoken form for another exercise is rejected
  await vis(page.locator("#new-name")).fill(`حرکت دیگر ${uniq}`);
  await vis(page.locator("#new-aliases")).fill(`لگ کرل ${uniq}`);
  await vis(page.getByRole("button", { name: "افزودن" })).click();
  await vis(page.getByText("قبلاً برای")).first().waitFor();
  step("dictionary: duplicate alias across entries rejected");

  await page.getByPlaceholder("جستجو در نام‌ها و مترادف‌ها").fill(`لگ کرل ${uniq}`);
  assert.equal(await vis(page.getByTestId("dictionary-entry")).count(), 1);
  await row.getByRole("button", { name: `ویرایش ${name}` }).click();
  const editRow = vis(page.getByTestId("dictionary-entry")).filter({ has: page.locator("form") });
  await editRow.locator(`input[id$="-aliases"]`).fill(`لگ‌کرل ${uniq}`);
  await editRow.getByRole("button", { name: "ذخیره" }).click();
  await vis(page.getByTestId("dictionary-entry")).filter({ hasText: `لگ‌کرل ${uniq}` }).waitFor();
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/p5-dictionary.png`, fullPage: true });
  await vis(page.getByRole("button", { name: `حذف ${name}` })).click();
  await page.getByRole("button", { name: "حذف شود" }).click();
  await page.waitForFunction((n) => ![...document.querySelectorAll('[data-testid="dictionary-entry"]')]
    .some((el) => el.textContent.includes(n)), name);
  step("dictionary: search, edit aliases, delete with confirmation");

  // --- program created from Telegram voice ---
  if (VOICE_STUDENT) {
    await page.goto(`${BASE}/programs?q=${encodeURIComponent(VOICE_STUDENT)}&status=all`);
    await vis(page.locator("main ul > li a")).first().click();
    await page.waitForURL(/\/programs\/[0-9a-f-]{36}$/);
    await vis(page.getByText("از ویس تلگرام")).waitFor();
    await vis(page.getByText("نسخه ۱", { exact: true })).waitFor();
    const text = await vis(page.locator("table")).first().innerText();
    assert.match(text, /پرس بالا سینه دمبل[\s\S]*۴[\s\S]*۱۵/);
    assert.match(text, /اسکوات\s+۴\s+—/); // reps not guessed
    if (SHOTS) await page.screenshot({ path: `${SHOTS}/p5-program.png`, fullPage: true });
    await vis(page.getByRole("link", { name: "ویرایش" })).click();
    await vis(page.getByRole("button", { name: "جزئیات بیشتر" })).first().click();
    await vis(page.getByText(/^متن خام:/)).first().waitFor();
    step("program from voice: badge, approved with PDF, values as said, raw text kept in editor");
  }
  console.log("ALL PASSED");
} finally {
  await browser.close();
}
