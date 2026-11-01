import { test } from "node:test";
import assert from "node:assert/strict";
import { isoToJalaliInput, parseDecimalInput, parseJalaliInput, toAsciiDigits } from "../lib/jalali.ts";

test("toAsciiDigits handles Persian and Arabic digits", () => {
  assert.equal(toAsciiDigits("۱۴۰۵/٠٨/۰۹"), "1405/08/09");
});

test("parseJalaliInput accepts common formats", () => {
  for (const s of ["1405/08/09", "۱۴۰۵/۸/۹", "1405-8-9", "1405.08.09", " ۱۴۰۵/۰۸/۰۹ "]) {
    assert.deepEqual(parseJalaliInput(s), { ok: true, iso: "2026-10-31" }, s);
  }
  assert.deepEqual(parseJalaliInput("1405/01/01"), { ok: true, iso: "2026-03-21" });
  assert.deepEqual(parseJalaliInput(""), { ok: true, iso: null });
});

test("parseJalaliInput rejects invalid dates", () => {
  for (const s of ["1405/13/01", "1405/07/31", "1403/12/31".replace("1403", "1404"), "abc", "05/08/09", "1405/08"]) {
    assert.deepEqual(parseJalaliInput(s), { ok: false }, s);
  }
});

test("isoToJalaliInput round-trips", () => {
  assert.equal(isoToJalaliInput("2026-10-31"), "1405/08/09");
  assert.equal(isoToJalaliInput(null), "");
  const back = parseJalaliInput(isoToJalaliInput("1995-05-01"));
  assert.deepEqual(back, { ok: true, iso: "1995-05-01" });
});

test("parseDecimalInput", () => {
  assert.deepEqual(parseDecimalInput("۸۲٫۵"), { ok: true, value: 82.5 });
  assert.deepEqual(parseDecimalInput("82,5"), { ok: true, value: 82.5 });
  assert.deepEqual(parseDecimalInput(""), { ok: true, value: null });
  assert.deepEqual(parseDecimalInput("12kg"), { ok: false });
  assert.deepEqual(parseDecimalInput("-3"), { ok: false });
});
