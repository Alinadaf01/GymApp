import { test } from "node:test";
import assert from "node:assert/strict";
import { formatJalaliDate, toPersianDigits } from "../lib/format.ts";

test("toPersianDigits converts ASCII digits", () => {
  assert.equal(toPersianDigits("4 ست 15 تایی"), "۴ ست ۱۵ تایی");
  assert.equal(toPersianDigits(1405), "۱۴۰۵");
});

test("formatJalaliDate converts ISO calendar dates without timezone shift", () => {
  assert.equal(formatJalaliDate("2026-10-31"), "۱۴۰۵/۰۸/۰۹");
  assert.equal(formatJalaliDate("2026-03-21"), "۱۴۰۵/۰۱/۰۱");
});

test("formatJalaliDate renders UTC timestamps in Tehran time", () => {
  // 21:00 UTC on Oct 30 is already Oct 31 in Tehran (UTC+3:30)
  assert.equal(formatJalaliDate("2026-10-30T21:00:00Z"), "۱۴۰۵/۰۸/۰۹");
});

test("formatJalaliDate handles empty values", () => {
  assert.equal(formatJalaliDate(null), "—");
  assert.equal(formatJalaliDate("not-a-date"), "—");
});
