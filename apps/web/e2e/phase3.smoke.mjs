// E2E smoke test for student management (phase 3).
//   E2E_USERNAME=coach E2E_PASSWORD=... node e2e/phase3.smoke.mjs
// Creates real records in the target database — run against a dev database only.
import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
// Self-signed test certificates (e.g. infra/tests/test-compose-stack.sh)
const IGNORE_TLS = !!process.env.E2E_IGNORE_HTTPS_ERRORS;

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const USER = process.env.E2E_USERNAME;
const PASS = process.env.E2E_PASSWORD;
const SHOTS = process.env.E2E_SCREENSHOTS;
assert.ok(USER && PASS, "set E2E_USERNAME and E2E_PASSWORD");

const step = (name) => console.log(`✓ ${name}`);
// Next.js keeps previous pages in the DOM (hidden via <Activity>): match visible elements only
const vis = (locator) => locator.filter({ visible: true });
const unique = Date.now().toString().slice(-6);
const LAST = `تستی${unique}`;
const PHONE_FA = `۰۹۱۲${[...unique].map((d) => "۰۱۲۳۴۵۶۷۸۹"[d]).join("")}۷`; // 11 digits

const browser = await chromium.launch();
try {
  const ctx = await browser.newContext({ ignoreHTTPSErrors: IGNORE_TLS, viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();

  await page.goto(`${BASE}/login`);
  await page.fill("#username", USER);
  await page.fill("#password", PASS);
  await page.click("button[type=submit]");
  await page.waitForURL(/\/dashboard$/);

  // Build a JPEG in the browser (canvas) to upload
  const jpeg = Buffer.from(
    (
      await page.evaluate(() => {
        const c = document.createElement("canvas");
        c.width = 1600;
        c.height = 1200;
        const g = c.getContext("2d");
        g.fillStyle = "#3b82f6";
        g.fillRect(0, 0, 1600, 1200);
        g.fillStyle = "#fff";
        g.beginPath();
        g.arc(800, 600, 400, 0, Math.PI * 2);
        g.fill();
        return c.toDataURL("image/jpeg", 0.8);
      })
    ).split(",")[1],
    "base64",
  );

  // --- create with validation ---
  await page.getByRole("link", { name: "افزودن شاگرد" }).first().click();
  await page.waitForURL(/\/students\/new$/);
  await page.getByRole("button", { name: "ثبت شاگرد" }).click();
  assert.equal(await page.locator("#first_name-error").textContent(), "نام الزامی است.");
  assert.equal(await page.locator("#last_name-error").textContent(), "نام خانوادگی الزامی است.");
  step("create form: required-field errors");

  await page.fill("#first_name", "سینا");
  await page.fill("#last_name", LAST);
  await page.fill("#phone", PHONE_FA);
  await page.fill("#birth_date", "۱۳۷۴/۲/۱۱");
  await page.fill("#start_date", "1405/13/01");
  await page.fill("#height_cm", "۱۸۰");
  await page.fill("#initial_weight_kg", "۸۸٫۵");
  await page.fill("#current_weight_kg", "۸۲٫۴");
  await page.selectOption("#gender", "male");
  await page.fill("#goal", "کاهش چربی و حفظ عضله");
  await page.fill("#limitations_notes", "درد خفیف زانوی راست");
  await page.getByRole("button", { name: "ثبت شاگرد" }).click();
  await page.locator("#start_date-error").getByText("تاریخ را به شکل ۱۴۰۵/۰۸/۰۹ وارد کنید.").waitFor();
  step("invalid Jalali date rejected client-side");
  await page.fill("#start_date", "۱۴۰۵/۰۸/۰۱");

  await page.setInputFiles('input[type=file]', { name: "me.jpg", mimeType: "image/jpeg", buffer: jpeg });
  await page.getByAltText("پیش‌نمایش تصویر").waitFor();
  await page.getByRole("button", { name: "ثبت شاگرد" }).click();
  await vis(page.getByText("رضایت شاگرد را تأیید کنید")).first().waitFor();
  step("photo requires consent");
  await page.getByLabel("رضایت شاگرد برای ثبت و نگهداری تصویر گرفته شده است.").check();
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/p3-form.png`, fullPage: true });
  await page.getByRole("button", { name: "ثبت شاگرد" }).click();

  await page.waitForURL(/\/students\/[0-9a-f-]{36}$/);
  const studentUrl = page.url();
  await vis(page.getByRole("heading", { name: `سینا ${LAST}` })).waitFor();
  await vis(page.getByText("۱۴۰۵/۰۸/۰۱")).first().waitFor();
  await vis(page.getByText("۸۲٫۴ کیلوگرم")).first().waitFor();
  const img = vis(page.getByAltText(`تصویر سینا ${LAST}`)).first();
  await img.waitFor();
  await page.waitForFunction((el) => el.complete && el.naturalWidth > 0, await img.elementHandle());
  assert.equal(await img.evaluate((el) => el.naturalWidth), 1024, "photo resized to 1024px");
  step("student created; profile shows Jalali date, weight and private photo");

  // Activity regression: the hidden "new" page must come back empty
  await vis(page.getByRole("link", { name: "شاگردان" })).first().click();
  await page.waitForURL(/\/students$/);
  await vis(page.getByRole("link", { name: "افزودن شاگرد" })).first().click();
  await page.waitForURL(/\/students\/new$/);
  assert.equal(await vis(page.locator("#first_name")).inputValue(), "");
  assert.equal(await vis(page.locator("#last_name")).inputValue(), "");
  assert.equal(await vis(page.getByAltText("پیش‌نمایش تصویر")).count(), 0);
  assert.equal(await vis(page.getByRole("button", { name: "ثبت شاگرد" })).isEnabled(), true);
  step("create form is empty again after a successful create (hidden-page state reset)");
  await page.goBack();
  await page.goBack();
  await page.waitForURL(studentUrl);

  // --- tabs ---
  await vis(page.getByText("درد خفیف زانوی راست")).first().waitFor();
  await vis(page.getByText("شاگرد جدید ثبت شد")).first().waitFor();
  await vis(page.getByRole("tab", { name: "برنامه‌ها" })).click();
  await vis(page.getByText("هنوز برنامه‌ای برای این شاگرد ثبت نشده است")).first().waitFor();
  assert.match(page.url(), /\?tab=programs$/);
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/p3-profile.png`, fullPage: true });
  step("profile tabs (overview/programs) work and tab is kept in URL");

  // --- edit ---
  await vis(page.getByRole("link", { name: "ویرایش" })).click();
  await page.waitForURL(/\/edit$/);
  assert.equal(await vis(page.locator("#start_date")).inputValue(), "1405/08/01");
  await vis(page.locator("#coach_notes")).fill("تمرکز روی فرم حرکت");
  await vis(page.getByRole("button", { name: "ذخیره تغییرات" })).click();
  await page.waitForURL(studentUrl);
  await vis(page.getByText("تمرکز روی فرم حرکت")).first().waitFor();
  await vis(page.getByRole("tab", { name: "تاریخچه" })).click();
  await vis(page.getByText("تغییر در: توضیحات مربی")).first().waitFor();
  step("edit saves; history shows changed field names");

  // --- list, search with Persian digits ---
  await page.goto(`${BASE}/students`);
  await page.getByPlaceholder("جستجو با نام یا موبایل").fill(PHONE_FA.slice(-5));
  await page.waitForURL(/q=/);
  await vis(page.getByRole("link", { name: `مشاهده پرونده سینا ${LAST}`, exact: true })).waitFor();
  // Wait for the debounced search result (the unfiltered list may still be on screen)
  for (let i = 0; i < 50 && (await vis(page.locator("tbody tr")).count()) !== 1; i++) await page.waitForTimeout(100);
  assert.equal(await vis(page.locator("tbody tr")).count(), 1);
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/p3-list.png`, fullPage: true });
  step("list search by Persian-digit phone finds the student");

  // --- archive & restore ---
  await page.goto(studentUrl);
  await vis(page.getByRole("button", { name: "بایگانی", exact: true })).click();
  await page.getByRole("alertdialog").getByText("حذف نمی‌شوند").waitFor();
  await page.getByRole("button", { name: "بله، بایگانی شود" }).click();
  await vis(page.getByRole("button", { name: "خروج از بایگانی" })).waitFor();

  await page.goto(`${BASE}/students?q=${encodeURIComponent(LAST)}`);
  await vis(page.getByText("شاگردی با این مشخصات پیدا نشد.")).first().waitFor();
  await page.goto(`${BASE}/students?q=${encodeURIComponent(LAST)}&status=archived`);
  await vis(page.getByRole("link", { name: `مشاهده پرونده سینا ${LAST}`, exact: true })).waitFor();
  step("archive hides from default list; visible under archived filter");

  await page.goto(studentUrl);
  await vis(page.getByRole("button", { name: "خروج از بایگانی" })).click();
  await vis(page.getByRole("button", { name: "بایگانی", exact: true })).waitFor();
  step("restore from archive");

  // Activity regression: an edit page kept hidden must not show stale status
  await page.goto(`${studentUrl}/edit`);
  assert.equal(await vis(page.locator("#status")).inputValue(), "active");
  await vis(page.getByRole("link", { name: "انصراف" })).click();
  await page.waitForURL(studentUrl);
  await vis(page.getByRole("button", { name: "بایگانی", exact: true })).click();
  await page.getByRole("button", { name: "بله، بایگانی شود" }).click();
  await vis(page.getByRole("button", { name: "خروج از بایگانی" })).waitFor();
  await vis(page.getByRole("link", { name: "ویرایش" })).click();
  await page.waitForURL(/\/edit$/);
  await page.waitForFunction(() =>
    [...document.querySelectorAll("#status")].some((el) => el.checkVisibility() && el.value === "archived"),
  );
  step("edit form refreshes after the record changed elsewhere (no stale overwrite)");
  await vis(page.getByRole("link", { name: "انصراف" })).click();
  await page.waitForURL(studentUrl);
  await vis(page.getByRole("button", { name: "خروج از بایگانی" })).click();
  await vis(page.getByRole("button", { name: "بایگانی", exact: true })).waitFor();
  await ctx.close();

  // --- mobile ---
  const m = await browser.newContext({ ignoreHTTPSErrors: IGNORE_TLS,
    viewport: { width: 390, height: 844 },
    isMobile: true,
    storageState: undefined,
  });
  const mp = await m.newPage();
  await mp.goto(`${BASE}/login`);
  await mp.fill("#username", USER);
  await mp.fill("#password", PASS);
  await mp.click("button[type=submit]");
  await mp.waitForURL(/\/dashboard$/);
  for (const url of ["/students", studentUrl.replace(BASE, ""), `${studentUrl.replace(BASE, "")}/edit`]) {
    await mp.goto(`${BASE}${url}`);
    await mp.waitForLoadState("networkidle");
    assert.ok(
      await mp.evaluate(() => document.documentElement.scrollWidth <= 390 /* real phone width; mobile emulation widens innerWidth to fit overflow */),
      `no horizontal scroll on ${url}`,
    );
  }
  await mp.goto(`${BASE}/students`);
  await vis(mp.getByRole("link", { name: "مشاهده پرونده" })).first().waitFor();
  if (SHOTS) await mp.screenshot({ path: `${SHOTS}/p3-list-mobile.png`, fullPage: true });
  await mp.goto(studentUrl);
  await vis(mp.getByRole("heading", { name: `سینا ${LAST}` })).waitFor();
  if (SHOTS) await mp.screenshot({ path: `${SHOTS}/p3-profile-mobile.png`, fullPage: true });
  step("mobile: list cards, profile and edit have no horizontal scroll");
  await m.close();

  console.log("ALL PASSED");
} finally {
  await browser.close();
}
