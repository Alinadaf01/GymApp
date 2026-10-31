// E2E smoke test for progress photos, measurements and charts (phase 6).
//   E2E_USERNAME=coach E2E_PASSWORD=... node e2e/phase6.smoke.mjs
// Creates records in the target DB — development database only.
import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const API = process.env.E2E_API_URL ?? "http://localhost:8000";
const USER = process.env.E2E_USERNAME;
const PASS = process.env.E2E_PASSWORD;
const SHOTS = process.env.E2E_SCREENSHOTS;
assert.ok(USER && PASS, "set E2E_USERNAME and E2E_PASSWORD");

const step = (name) => console.log(`✓ ${name}`);
const vis = (locator) => locator.filter({ visible: true });
const uniq = Date.now().toString().slice(-5);

async function login(page) {
  await page.goto(`${BASE}/login`);
  await page.fill("#username", USER);
  await page.fill("#password", PASS);
  await page.click("button[type=submit]");
  await page.waitForURL(/\/dashboard$/);
}

async function makeJpeg(page, color, label) {
  const b64 = await page.evaluate(([c, l]) => {
    const cv = document.createElement("canvas");
    cv.width = 900; cv.height = 1200;
    const g = cv.getContext("2d");
    g.fillStyle = c; g.fillRect(0, 0, 900, 1200);
    g.fillStyle = "#fff"; g.font = "120px sans-serif"; g.fillText(l, 200, 600);
    return cv.toDataURL("image/jpeg", 0.85).split(",")[1];
  }, [color, label]);
  return { name: `${label}.jpg`, mimeType: "image/jpeg", buffer: Buffer.from(b64, "base64") };
}

async function imagesLoaded(page, selector) {
  return page.evaluate((sel) => [...document.querySelectorAll(sel)]
    .filter((i) => i.checkVisibility()).every((i) => i.complete && i.naturalWidth > 0), selector);
}

const browser = await chromium.launch();
try {
  const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
  await login(page);
  const student = await page.evaluate(async ([api, last]) => {
    const r = await fetch(`${api}/api/students`, {
      method: "POST", credentials: "include",
      headers: { "Content-Type": "application/json", "X-Requested-With": "fetch" },
      body: JSON.stringify({ first_name: "نیما", last_name: last, current_weight_kg: 90 }),
    });
    return r.json();
  }, [API, `پیشرفت${uniq}`]);
  const url = `${BASE}/students/${student.id}`;

  // --- photos ---
  await page.goto(`${url}?tab=photos`);
  const form = vis(page.locator("form")).first();
  await form.getByLabel("تاریخ عکس (شمسی)").fill("۱۴۰۵/۰۶/۰۱");
  await form.getByLabel("عکس روبه‌رو").setInputFiles(await makeJpeg(page, "#2a78d6", "F1"));
  await form.getByLabel("عکس نیم‌رخ").setInputFiles(await makeJpeg(page, "#1baf7a", "S1"));
  await form.getByRole("button", { name: "ثبت عکس‌ها" }).click();
  await vis(page.getByText("رضایت شاگرد برای ثبت تصاویر را تأیید کنید.")).waitFor();
  step("photos require the student's consent");
  await form.getByLabel(/رضایت شاگرد/).check();
  await form.getByRole("button", { name: "ثبت عکس‌ها" }).click();
  await vis(page.getByTestId("album-date")).first().waitFor();
  const album1 = vis(page.getByTestId("album-date")).first();
  assert.equal(await album1.getByRole("button", { name: /نمایش عکس/ }).count(), 2);
  assert.equal(await album1.getByText("ثبت نشده").count(), 1); // back view optional
  await page.waitForFunction(() => [...document.querySelectorAll('[data-testid="album-date"] img')]
    .every((i) => i.complete && i.naturalWidth > 0));
  step("upload 2 of 3 views for one date; album shows them, missing view marked");

  await form.getByLabel("تاریخ عکس (شمسی)").fill("۱۴۰۵/۰۸/۰۱");
  await form.getByLabel("عکس روبه‌رو").setInputFiles(await makeJpeg(page, "#eb6834", "F2"));
  await form.getByLabel("عکس پشت").setInputFiles(await makeJpeg(page, "#6250d6", "B2"));
  await form.getByRole("button", { name: "ثبت عکس‌ها" }).click();
  const compare = vis(page.getByTestId("photo-compare"));
  await compare.waitFor();
  assert.equal(await compare.getByLabel("تاریخ اول").inputValue(), "2026-08-23"); // oldest
  assert.equal(await compare.getByLabel("تاریخ دوم").inputValue(), "2026-10-23"); // newest
  assert.equal(await compare.getByRole("button", { name: /نمایش عکس/ }).count(), 4); // front×2, back(B), side(A)
  assert.equal(await compare.getByText("ثبت نشده").count(), 2);
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/p6-photos.png`, fullPage: true });
  step("compare two dates side by side (oldest vs newest by default)");

  // duplicate view on same date is refused
  await form.getByLabel("تاریخ عکس (شمسی)").fill("۱۴۰۵/۰۸/۰۱");
  await form.getByLabel("عکس روبه‌رو").setInputFiles(await makeJpeg(page, "#000", "X"));
  await form.getByRole("button", { name: "ثبت عکس‌ها" }).click();
  await vis(page.getByText(/ابتدا آن را حذف کنید/)).waitFor();
  step("one photo per view and date");

  // lightbox + delete
  await vis(page.getByTestId("album-date")).first().getByRole("button", { name: /نمایش عکس پشت/ }).click();
  const dialog = page.getByRole("dialog");
  await dialog.waitFor();
  await page.waitForFunction(() => {
    const i = document.querySelector('[role="dialog"] img');
    return i && i.complete && i.naturalWidth === 900;
  });
  await dialog.getByRole("button", { name: "حذف این عکس" }).click();
  await page.getByRole("button", { name: "حذف شود" }).click();
  await dialog.waitFor({ state: "detached" });
  // wait for the album to reload: newest date keeps only its front photo
  await page.waitForFunction(() => {
    const first = [...document.querySelectorAll('[data-testid="album-date"]')].find((el) => el.checkVisibility());
    return first && first.querySelectorAll('button[aria-label^="نمایش عکس"]').length === 1
      && !first.querySelector('button[aria-label^="نمایش عکس پشت"]');
  });
  step("full-size view (private, original kept) and delete with confirmation");

  // --- measurements & charts ---
  await vis(page.getByRole("tab", { name: "روند تغییرات" })).click();
  const mform = vis(page.locator("form")).first();
  async function addMeasure(date, values) {
    await mform.getByLabel("تاریخ اندازه‌گیری").fill(date);
    for (const [label, v] of Object.entries(values)) await mform.getByLabel(label, { exact: true }).fill(v);
    await mform.getByRole("button", { name: "ثبت اندازه‌ها" }).click();
    await vis(page.getByText("اندازه‌ها ثبت شدند.")).last().waitFor();
    await page.waitForTimeout(300);
  }
  await mform.getByRole("button", { name: "ثبت اندازه‌ها" }).click();
  await vis(page.getByText("حداقل یک اندازه را وارد کنید.")).waitFor();
  await addMeasure("۱۴۰۵/۰۶/۰۱", { "وزن (kg)": "۸۸٫۵", "دور کمر (cm)": "96", "دور بازو (cm)": "36" });
  assert.equal(await vis(page.getByText("برای رسم نمودار حداقل دو اندازه‌گیری در دو تاریخ مختلف لازم است.")).count(), 3);
  step("one measurement: charts explain they need two real points (nothing fabricated)");

  await addMeasure("۱۴۰۵/۰۷/۰۱", { "وزن (kg)": "86", "دور کمر (cm)": "93" });
  await addMeasure("۱۴۰۵/۰۸/۰۵", { "وزن (kg)": "84.2" });
  const charts = vis(page.locator("figure"));
  const weightChart = charts.filter({ hasText: "وزن" }).first();
  await weightChart.locator("svg path").waitFor();
  assert.equal(await weightChart.locator("svg circle").count(), 3);
  assert.equal(await charts.filter({ hasText: "دور کمر" }).locator("svg circle").count(), 2);
  assert.equal(await charts.filter({ hasText: "دور بازو" }).getByText(/حداقل دو اندازه‌گیری/).count(), 1);
  assert.match(await weightChart.locator("figcaption").innerText(), /−۴٫۳ کیلوگرم/);
  // hover -> tooltip with Jalali date and value
  const overlay = weightChart.locator("svg rect");
  const box = await overlay.boundingBox();
  await overlay.hover({ position: { x: box.width - 30, y: box.height / 2 } }); // scrolls into view
  await vis(weightChart.getByRole("status")).waitFor();
  assert.match(await weightChart.getByRole("status").innerText(), /۱۴۰۵\/۰۸\/۰۵[\s\S]*۸۴٫۲ کیلوگرم/);
  // Each chart stays inside its own column (regression: charts overflowed into each other)
  const overflow = await page.evaluate(() => [...document.querySelectorAll("figure")].filter((f) => f.checkVisibility())
    .map((f) => { const s = f.querySelector("svg"); return s ? s.getBoundingClientRect().width - f.getBoundingClientRect().width : 0; }));
  assert.ok(overflow.every((d) => d <= 1), `charts overflow their figure: ${overflow}`);
  step("charts: real points only, per-metric (no dual axis), change shown, hover tooltip");

  // header current weight follows latest measurement
  await vis(page.getByText("۸۴٫۲ کیلوگرم")).first().waitFor();
  const header = vis(page.locator("dl")).first();
  assert.match(await header.innerText(), /۸۴٫۲ کیلوگرم/);
  step("profile header current weight updated from latest measurement");

  const table = vis(page.getByTestId("measurements-table"));
  assert.equal(await table.locator("tbody tr").count(), 3);
  await table.getByRole("button", { name: "ویرایش اندازه‌گیری ۱۴۰۵/۰۸/۰۵" }).click();
  await table.getByLabel("وزن (kg)").fill("84.6");
  await table.getByRole("button", { name: "ذخیره" }).click();
  await vis(page.getByText("ذخیره شد.")).waitFor();
  await page.waitForFunction(() => document.body.innerText.includes("۸۴٫۶ کیلوگرم"));
  await table.getByRole("button", { name: "حذف اندازه‌گیری ۱۴۰۵/۰۸/۰۵" }).click();
  await page.getByRole("button", { name: "حذف شود" }).click();
  await page.waitForFunction(() => document.querySelectorAll('[data-testid="measurements-table"] tbody tr').length === 2);
  assert.match(await header.innerText(), /۸۶ کیلوگرم/);
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/p6-trends.png`, fullPage: true });
  step("edit and delete measurements; current weight recalculated");

  // --- history ---
  await vis(page.getByRole("tab", { name: "تاریخچه" })).click();
  await vis(page.getByText(/عکس پیشرفت ثبت شد \(روبه‌رو\)/)).first().waitFor();
  await vis(page.getByText("عکس پیشرفت حذف شد (پشت)")).waitFor();
  await vis(page.getByText("اندازه‌گیری حذف شد")).waitFor();
  step("history lists photo and measurement events with view and date");

  // --- mobile ---
  const m = await (await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true })).newPage();
  await login(m);
  for (const tab of ["photos", "trends"]) {
    await m.goto(`${url}?tab=${tab}`);
    await m.waitForLoadState("networkidle");
    await m.waitForTimeout(300);
    assert.ok(await m.evaluate(() => document.documentElement.scrollWidth <= 390 /* real phone width; mobile emulation widens innerWidth to fit overflow */
      && [...document.querySelectorAll("main *")].filter((el) => el.checkVisibility() && !el.closest(".overflow-x-auto"))
        .every((el) => el.getBoundingClientRect().right <= window.innerWidth + 1)), `no h-overflow ${tab}`);
    if (SHOTS) await m.screenshot({ path: `${SHOTS}/p6-${tab}-mobile.png`, fullPage: true });
  }
  assert.ok(await imagesLoaded(m, '[data-testid="album-date"] img'));
  step("mobile: photos and trends without horizontal scroll");
  console.log("ALL PASSED");
} finally {
  await browser.close();
}
