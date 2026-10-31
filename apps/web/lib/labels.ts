import type { ExecutionType, Gender, PhotoView, ProgramStatus, ProgramType, StudentStatus } from "./types";

export const studentStatusLabel: Record<StudentStatus, string> = {
  active: "فعال",
  inactive: "غیرفعال",
  archived: "بایگانی",
};

export const genderLabel: Record<Gender, string> = {
  male: "مرد",
  female: "زن",
  other: "سایر",
};

export const programTypeLabel: Record<ProgramType, string> = {
  workout: "تمرینی",
  nutrition: "غذایی",
  supplement: "مکمل",
  vitamin: "ویتامین",
};

export const programStatusLabel: Record<ProgramStatus, string> = {
  draft: "پیش‌نویس",
  approved: "تأییدشده",
  archived: "بایگانی",
};

export const photoViewLabel: Record<PhotoView, string> = { front: "روبه‌رو", back: "پشت", side: "نیم‌رخ" };
export const PHOTO_VIEWS: PhotoView[] = ["front", "back", "side"];

export const MEASUREMENT_FIELDS = [
  { key: "weight_kg", label: "وزن", unit: "کیلوگرم" },
  { key: "arm_cm", label: "دور بازو", unit: "سانتی‌متر" },
  { key: "chest_cm", label: "دور سینه", unit: "سانتی‌متر" },
  { key: "waist_cm", label: "دور کمر", unit: "سانتی‌متر" },
  { key: "abdomen_cm", label: "دور شکم", unit: "سانتی‌متر" },
  { key: "thigh_cm", label: "دور ران", unit: "سانتی‌متر" },
  { key: "hip_cm", label: "دور باسن", unit: "سانتی‌متر" },
] as const;
export type MeasurementKey = (typeof MEASUREMENT_FIELDS)[number]["key"];

export const executionTypeLabel: Record<ExecutionType, string> = {
  reps: "تکرار",
  time: "زمان",
  distance: "مسافت",
  combined: "ترکیبی",
  free: "آزاد",
};

export const WEIGHT_UNITS = [
  { value: "kg", label: "کیلوگرم" },
  { value: "lb", label: "پوند" },
];
export const DISTANCE_UNITS = [
  { value: "m", label: "متر" },
  { value: "km", label: "کیلومتر" },
];
const UNIT_LABELS: Record<string, string> = { kg: "کیلوگرم", lb: "پوند", m: "متر", km: "کیلومتر" };
export function unitLabel(unit: string | null | undefined): string {
  return unit ? (UNIT_LABELS[unit] ?? unit) : "";
}

const activityLabels: Record<string, string> = {
  "auth.admin_created": "حساب مدیر ساخته شد",
  "auth.password_changed": "رمز عبور تغییر کرد",
  "auth.password_reset": "رمز عبور بازنشانی شد",
  "student.created": "شاگرد جدید ثبت شد",
  "student.updated": "پرونده شاگرد ویرایش شد",
  "student.archived": "شاگرد بایگانی شد",
  "student.restored": "شاگرد از بایگانی خارج شد",
  "student.activated": "شاگرد فعال شد",
  "student.deactivated": "شاگرد غیرفعال شد",
  "student.photo_updated": "تصویر پروفایل ثبت شد",
  "student.photo_removed": "تصویر پروفایل حذف شد",
  "program.created": "برنامه جدید ایجاد شد",
  "program.approved": "برنامه تأیید شد",
  "program.duplicated": "برنامه کپی شد",
  "program.archived": "برنامه بایگانی شد",
  "program.updated": "برنامه تأییدشده ویرایش شد",
  "program.draft_deleted": "پیش‌نویس برنامه حذف شد",
  "settings.pdf_template_updated": "تنظیمات سربرگ PDF تغییر کرد",
  "settings.logo_updated": "لوگو تغییر کرد",
  "dictionary.created": "حرکت به فرهنگ لغت اضافه شد",
  "pdf.generated": "PDF تولید شد",
  "photo.uploaded": "عکس پیشرفت ثبت شد",
  "measurement.created": "اندازه‌های بدن ثبت شد",
  "measurement.updated": "اندازه‌گیری ویرایش شد",
  "measurement.deleted": "اندازه‌گیری حذف شد",
  "photo.deleted": "عکس پیشرفت حذف شد",
};

export function activityLabel(action: string): string {
  return activityLabels[action] ?? action;
}

/** Persian names of student fields (used for "what changed" in history). */
export const studentFieldLabel: Record<string, string> = {
  first_name: "نام",
  last_name: "نام خانوادگی",
  phone: "موبایل",
  birth_date: "تاریخ تولد",
  gender: "جنسیت",
  height_cm: "قد",
  initial_weight_kg: "وزن اولیه",
  current_weight_kg: "وزن فعلی",
  training_history: "سابقه تمرینی",
  goal: "هدف تمرینی",
  limitations_notes: "محدودیت‌ها",
  start_date: "تاریخ شروع",
  coach_notes: "توضیحات مربی",
};
