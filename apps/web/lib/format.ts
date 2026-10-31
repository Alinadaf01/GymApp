import { toJalaali } from "jalaali-js";

const PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹";

/** Convert ASCII digits to Persian digits for display. */
export function toPersianDigits(value: string | number): string {
  return String(value).replace(/[0-9]/g, (d) => PERSIAN_DIGITS[Number(d)]);
}

/**
 * Format a calendar date (ISO "YYYY-MM-DD" or Date) as Jalali "۱۴۰۵/۰۸/۰۹".
 * ISO date strings are parsed as calendar dates (no timezone shift).
 */
export function formatJalaliDate(input: string | Date | null | undefined): string {
  if (!input) return "—";
  let gy: number, gm: number, gd: number;
  if (typeof input === "string" && /^\d{4}-\d{2}-\d{2}$/.test(input)) {
    [gy, gm, gd] = input.split("-").map(Number);
  } else {
    const d = typeof input === "string" ? new Date(input) : input;
    if (Number.isNaN(d.getTime())) return "—";
    // Show timestamps in Tehran time
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone: "Asia/Tehran",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(d);
    [gy, gm, gd] = parts.split("-").map(Number);
  }
  const { jy, jm, jd } = toJalaali(gy, gm, gd);
  const pad = (n: number) => String(n).padStart(2, "0");
  return toPersianDigits(`${jy}/${pad(jm)}/${pad(jd)}`);
}

/** Format a number with Persian digits and grouping, e.g. 1250 -> "۱٬۲۵۰". */
export function formatNumber(value: number | string | null | undefined, fractionDigits = 1): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(n)) return "—";
  return new Intl.NumberFormat("fa-IR", { maximumFractionDigits: fractionDigits }).format(n);
}
