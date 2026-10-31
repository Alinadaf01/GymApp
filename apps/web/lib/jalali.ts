import { isValidJalaaliDate, toGregorian, toJalaali } from "jalaali-js";

const DIGITS_FA = "۰۱۲۳۴۵۶۷۸۹";
const DIGITS_AR = "٠١٢٣٤٥٦٧٨٩";

/** Persian/Arabic digits -> ASCII. */
export function toAsciiDigits(value: string): string {
  return value.replace(/[۰-۹٠-٩]/g, (d) => {
    const fa = DIGITS_FA.indexOf(d);
    return String(fa >= 0 ? fa : DIGITS_AR.indexOf(d));
  });
}

const pad = (n: number) => String(n).padStart(2, "0");

/** ISO "YYYY-MM-DD" -> Jalali "1405/08/09" (ASCII digits, for inputs). */
export function isoToJalaliInput(iso: string | null | undefined): string {
  if (!iso) return "";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return "";
  const { jy, jm, jd } = toJalaali(Number(m[1]), Number(m[2]), Number(m[3]));
  return `${jy}/${pad(jm)}/${pad(jd)}`;
}

export type ParsedDate = { ok: true; iso: string | null } | { ok: false };

/**
 * Parse a coach-typed Jalali date ("۱۴۰۵/۸/۹", "1405-08-09", "1405.8.9").
 * Empty input is valid and means "no date".
 */
export function parseJalaliInput(input: string): ParsedDate {
  const v = toAsciiDigits(input).trim();
  if (!v) return { ok: true, iso: null };
  const m = /^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})$/.exec(v);
  if (!m) return { ok: false };
  const [jy, jm, jd] = [Number(m[1]), Number(m[2]), Number(m[3])];
  if (!isValidJalaaliDate(jy, jm, jd)) return { ok: false };
  const { gy, gm, gd } = toGregorian(jy, jm, jd);
  return { ok: true, iso: `${gy}-${pad(gm)}-${pad(gd)}` };
}

/** Parse an optional decimal typed with Persian or ASCII digits ("۸۲٫۵", "82,5"). */
export function parseDecimalInput(input: string): { ok: true; value: number | null } | { ok: false } {
  const v = toAsciiDigits(input).trim().replace(/[٫,]/g, ".");
  if (!v) return { ok: true, value: null };
  if (!/^\d+(\.\d+)?$/.test(v)) return { ok: false };
  return { ok: true, value: Number(v) };
}
