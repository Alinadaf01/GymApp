// E2E smoke test for programs + PDF (phase 4).
//   E2E_USERNAME=coach E2E_PASSWORD=... node e2e/phase4.smoke.mjs
// Creates real records — run against a development database only.
import { createRequire } from "node:module";
import assert from "node:assert/strict";
import { writeFileSync } from "node:fs";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
// Self-signed test certificates (e.g. infra/tests/test-compose-stack.sh)
const IGNORE_TLS = !!process.env.E2E_IGNORE_HTTPS_ERRORS;

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const API = process.env.E2E_API_URL ?? "http://localhost:8000";
const USER = process.env.E2E_USERNAME;
const PASS = process.env.E2E_PASSWORD;
const SHOTS = process.env.E2E_SCREENSHOTS;
assert.ok(USER && PASS, "set E2E_USERNAME and E2E_PASSWORD");

const step = (name) => console.log(`✓ ${name}`);
const vis = (locator) => locator.filter({ visible: true });
const uniq = Date.now().toString().slice(-5);

const browser = await chromium.launch();
try {
  const ctx = await browser.newContext({ ignoreHTTPSErrors: IGNORE_TLS, viewport: { width: 1366, height: 900 } });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/login`);
  await page.fill("#username", USER);
  await page.fill("#password", PASS);
  await page.click("button[type=submit]");
  await page.waitForURL(/\/dashboard$/);

  // Setup: a student (through the API, with the session cookie)
  const student = await page.evaluate(async ([api, last]) => {
    const r = await fetch(`${api}/api/students`, {
      method: "POST", credentials: "include",
      headers: { "Content-Type": "application/json", "X-Requested-With": "fetch" },
      body: JSON.stringify({ first_name: "آرمان", last_name: last }),
    });
    return r.json();
  }, [API, `برنامه‌دار${uniq}`]);
  const NAME = student.full_name;

  // --- create a workout draft from the student profile ---
  await page.goto(`${BASE}/students/${student.id}?tab=programs`);
  await vis(page.getByRole("link", { name: "برنامه جدید" })).click();
  await page.waitForURL(/\/programs\/new\?student=/);
  await vis(page.getByText(NAME)).first().waitFor();
  await page.waitForFunction(() => document.querySelector("#program-period")?.value === "1");
  assert.equal(await vis(page.locator("#program-title")).inputValue(), "برنامه تمرینی دوره ۱");
  await vis(page.locator("#program-start")).fill("۱۴۰۵/۰۸/۱۰");
  await vis(page.getByRole("button", { name: "ساخت پیش‌نویس و ادامه" })).click();
  await page.waitForURL(/\/programs\/[0-9a-f-]{36}\/edit$/);
  const programId = page.url().split("/").at(-2);
  step("new program form: student preselected, period + title suggested, draft created");

  // --- editor ---
  const session = (i) => vis(page.getByTestId("session-card")).nth(i);
  const exercise = (s, i) => session(s).getByTestId("exercise-row").nth(i);
  const fill = (loc, label, value) => loc.getByLabel(label, { exact: true }).fill(value);

  await vis(page.getByRole("button", { name: "ذخیره" })).click();
  await vis(page.getByText("عنوان جلسه الزامی است.")).waitFor();
  await vis(page.getByText("نام حرکت الزامی است.")).waitFor();
  step("editor validation: empty session/exercise names rejected");

  await fill(session(0), "جلسه اول", "سینه و پشت بازو");
  await fill(exercise(0, 0), "نام حرکت", "پرس بالا سینه دمبل");
  await fill(exercise(0, 0), "ست", "۴");
  await fill(exercise(0, 0), "تکرار", "۱۵");
  await session(0).getByRole("button", { name: "افزودن حرکت" }).click();
  await fill(exercise(0, 1), "نام حرکت", "پرس سینه دستگاه");
  await fill(exercise(0, 1), "ست", "3");
  await fill(exercise(0, 1), "تکرار", "12-10-8");
  await fill(exercise(0, 1), "وزنه", "۴۰");
  await fill(exercise(0, 1), "استراحت (ثانیه)", "60");
  await fill(exercise(0, 1), "توضیحات", "اجرای کنترل‌شده");
  await exercise(0, 1).getByRole("button", { name: "انتقال حرکت به بالا" }).click();
  assert.equal(await exercise(0, 0).getByLabel("نام حرکت", { exact: true }).inputValue(), "پرس سینه دستگاه");

  await vis(page.getByRole("button", { name: "افزودن جلسه" })).click();
  await fill(session(1), "جلسه دوم", "پا");
  await fill(exercise(1, 0), "نام حرکت", "اسکوات");
  await fill(exercise(1, 0), "ست", "4"); // reps intentionally empty
  await vis(page.getByText("تغییرات ذخیره نشده")).waitFor();
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/p4-editor.png`, fullPage: true });
  await vis(page.getByRole("button", { name: "ذخیره" })).click();
  await page.waitForURL(new RegExp(`/programs/${programId}$`));
  step("editor: two sessions, reorder, Persian digits, save");

  // --- view (draft) ---
  await vis(page.getByText("این برنامه پیش‌نویس است")).waitFor();
  const rows = vis(page.locator("table")).first().locator("tbody tr");
  assert.equal(await rows.count(), 2);
  assert.match(await rows.nth(0).innerText(), /پرس سینه دستگاه[\s\S]*۳[\s\S]*۱۲-۱۰-۸[\s\S]*۴۰ کیلوگرم[\s\S]*۱ دقیقه/);
  const squatRow = await vis(page.locator("table")).nth(1).locator("tbody tr").first().innerText();
  assert.match(squatRow, /اسکوات\s+۴\s+—/); // reps not guessed
  step("view: values shown as entered, missing reps shown as —");

  // --- approve + PDF ---
  await vis(page.getByRole("button", { name: "تأیید و ساخت PDF" })).click();
  await vis(page.getByText("نسخه ۱", { exact: true })).waitFor({ timeout: 30000 });
  await vis(page.getByText("تأییدشده")).first().waitFor();
  const pdf1 = await vis(page.getByRole("link", { name: "دانلود" })).first().getAttribute("href");
  const r1 = await page.request.get(pdf1);
  assert.equal(r1.status(), 200);
  assert.ok((await r1.body()).subarray(0, 4).toString() === "%PDF");
  assert.match(r1.headers()["content-disposition"], /^attachment/);
  const viewHref = await vis(page.getByRole("link", { name: "مشاهده و چاپ" })).first().getAttribute("href");
  assert.match((await page.request.get(viewHref)).headers()["content-disposition"], /^inline/);
  if (SHOTS) writeFileSync(`${SHOTS}/p4-v1.pdf`, await r1.body());
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/p4-view.png`, fullPage: true });
  step("approve creates PDF v1; download (attachment) and print view (inline) work");

  // PDF is private: a fresh browser context without the cookie gets 401
  const anon = await browser.newContext();
  assert.equal((await anon.request.get(pdf1)).status(), 401);
  await anon.close();
  step("PDF not accessible without login");

  // --- edit approved program -> outdated -> v2, v1 kept ---
  await vis(page.getByRole("link", { name: "ویرایش" })).click();
  await page.waitForURL(/\/edit$/);
  await vis(page.getByText("این برنامه تأیید شده است")).waitFor();
  await vis(page.getByLabel("عنوان", { exact: true })).fill("برنامه تمرینی دوره ۱ (اصلاح‌شده)");
  await vis(page.getByRole("button", { name: "ذخیره" })).click();
  await page.waitForURL(new RegExp(`/programs/${programId}$`));
  await vis(page.getByText("برنامه بعد از ساخت آخرین PDF تغییر کرده است")).waitFor();
  await vis(page.getByText("قدیمی‌تر از برنامه")).waitFor();
  await vis(page.getByRole("button", { name: "ساخت PDF جدید" })).click();
  await vis(page.getByText("نسخه ۲", { exact: true })).waitFor({ timeout: 30000 });
  assert.equal(await vis(page.getByText(/^نسخه [۰-۹]+$/)).count(), 2);
  step("editing approved program marks PDF outdated; new version v2 created, v1 kept");

  // --- duplicate for next period ---
  await vis(page.getByRole("button", { name: "کپی برای دوره بعد" })).click();
  await page.waitForURL(/\/programs\/[0-9a-f-]{36}\/edit$/);
  const copyId = page.url().split("/").at(-2);
  assert.notEqual(copyId, programId);
  assert.equal(await vis(page.getByLabel("شماره دوره", { exact: true })).inputValue(), "2");
  assert.equal(await vis(page.getByLabel("تاریخ شروع (شمسی، مثل ۱۴۰۵/۰۸/۰۱)", { exact: true })).inputValue(), "");
  assert.equal(await exercise(0, 0).getByLabel("نام حرکت", { exact: true }).inputValue(), "پرس سینه دستگاه");
  await fill(exercise(0, 0), "وزنه", "45");
  await vis(page.getByRole("button", { name: "ذخیره" })).click();
  await page.waitForURL(new RegExp(`/programs/${copyId}$`));
  await page.goto(`${BASE}/programs/${programId}`);
  assert.match(await vis(page.locator("table")).first().locator("tbody tr").first().innerText(), /۴۰ کیلوگرم/);
  step("duplicate: new draft (period 2, no dates); editing the copy leaves the source untouched");

  // --- archive original ---
  await vis(page.getByRole("button", { name: "بایگانی" })).click();
  await page.getByRole("button", { name: "بایگانی شود" }).click();
  await vis(page.getByText("بایگانی", { exact: true })).first().waitFor();
  assert.equal(await vis(page.getByRole("link", { name: "ویرایش" })).count(), 0);
  step("archive locks editing");

  // --- delete the draft copy ---
  await page.goto(`${BASE}/programs/${copyId}`);
  await vis(page.getByRole("button", { name: "حذف پیش‌نویس" })).click();
  await page.getByRole("button", { name: "حذف شود" }).click();
  await page.waitForURL(new RegExp(`/students/${student.id}\\?tab=programs`));
  step("draft can be deleted (with confirmation)");

  // --- nutrition program ---
  await page.goto(`${BASE}/programs/new?student=${student.id}`);
  await vis(page.getByRole("radio", { name: "غذایی" })).click();
  await page.waitForFunction(() => document.querySelector("#program-title")?.value === "برنامه غذایی دوره ۱");
  await vis(page.getByRole("button", { name: "ساخت پیش‌نویس و ادامه" })).click();
  await page.waitForURL(/\/edit$/);
  const meal = vis(page.getByTestId("meal-row")).first();
  await meal.getByLabel("وعده", { exact: true }).fill("صبحانه");
  await meal.getByLabel("ساعت", { exact: true }).fill("08:00");
  await meal.getByLabel("مواد غذایی و مقدار", { exact: true }).fill("۲ عدد تخم‌مرغ\nنان سنگک");
  await vis(page.getByRole("button", { name: "ذخیره" })).click();
  await page.waitForURL(/\/programs\/[0-9a-f-]{36}$/);
  await vis(page.getByRole("button", { name: "تأیید و ساخت PDF" })).click();
  await vis(page.getByText("نسخه ۱", { exact: true })).waitFor({ timeout: 30000 });
  step("nutrition program: create, edit meals, approve with PDF");

  // Activity regression: new-program form is clean again
  await vis(page.getByRole("link", { name: "برنامه‌ها" })).first().click();
  await page.waitForURL(/\/programs$/);
  await vis(page.getByRole("link", { name: "ثبت برنامه جدید" })).click();
  await page.waitForURL(/\/programs\/new$/);
  assert.equal(await vis(page.getByLabel("جستجوی شاگرد", { exact: true })).count(), 1, "student picker visible (not preselected)");
  assert.equal(await vis(page.locator("#program-start")).inputValue(), "");
  step("new-program form resets after use");

  // --- programs list filters ---
  await page.goto(`${BASE}/programs?type=nutrition&q=${encodeURIComponent(student.last_name)}`);
  await vis(page.getByRole("link", { name: /برنامه غذایی دوره ۱/ })).waitFor();
  assert.equal(await vis(page.locator("main ul > li")).count(), 1);
  await page.goto(`${BASE}/programs?status=archived&q=${encodeURIComponent(student.last_name)}`);
  await vis(page.getByRole("link", { name: /اصلاح‌شده/ })).waitFor();
  step("programs list: type/status/search filters");

  // --- settings: template ---
  await page.goto(`${BASE}/settings`);
  await vis(page.locator("#club_name")).fill("مجموعه ورزشی Basharnia");
  await vis(page.locator("#coach_name")).fill("مربی آزمایشی");
  await vis(page.getByRole("button", { name: "ذخیره سربرگ" })).click();
  await vis(page.getByText("تنظیمات سربرگ ذخیره شد")).waitFor();
  step("settings: PDF letterhead saved");
  await ctx.close();

  // --- mobile ---
  const m = await browser.newContext({ ignoreHTTPSErrors: IGNORE_TLS, viewport: { width: 390, height: 844 }, isMobile: true });
  const mp = await m.newPage();
  await mp.goto(`${BASE}/login`);
  await mp.fill("#username", USER);
  await mp.fill("#password", PASS);
  await mp.click("button[type=submit]");
  await mp.waitForURL(/\/dashboard$/);
  for (const url of [`/programs/${programId}`, `/programs`, `/programs/new`, `/settings`]) {
    await mp.goto(`${BASE}${url}`);
    await mp.waitForLoadState("networkidle");
    assert.ok(await mp.evaluate(() => document.documentElement.scrollWidth <= 390 /* real phone width; mobile emulation widens innerWidth to fit overflow */), `no h-scroll ${url}`);
  }
  // an editable program on mobile
  const dup = await mp.evaluate(async ([api, id]) => {
    const r = await fetch(`${api}/api/programs/${id}/duplicate`, {
      method: "POST", credentials: "include", headers: { "X-Requested-With": "fetch" } });
    return r.json();
  }, [API, programId]);
  await mp.goto(`${BASE}/programs/${dup.id}/edit`);
  await vis(mp.getByTestId("exercise-row")).first().waitFor();
  assert.ok(await mp.evaluate(() => document.documentElement.scrollWidth <= 390 /* real phone width; mobile emulation widens innerWidth to fit overflow */), "no h-scroll editor");
  if (SHOTS) await mp.screenshot({ path: `${SHOTS}/p4-editor-mobile.png`, fullPage: true });
  step("mobile: program pages and editor have no horizontal scroll");
  await m.close();

  console.log("ALL PASSED");
} finally {
  await browser.close();
}
