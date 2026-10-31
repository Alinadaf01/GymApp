import type { ProgramStatus, ProgramType, StudentStatus } from "./types";

export const studentStatusLabel: Record<StudentStatus, string> = {
  active: "فعال",
  inactive: "غیرفعال",
  archived: "بایگانی",
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

const activityLabels: Record<string, string> = {
  "auth.admin_created": "حساب مدیر ساخته شد",
  "auth.password_changed": "رمز عبور تغییر کرد",
  "auth.password_reset": "رمز عبور بازنشانی شد",
  "student.created": "شاگرد جدید ثبت شد",
  "student.updated": "پرونده شاگرد ویرایش شد",
  "student.archived": "شاگرد بایگانی شد",
  "program.created": "برنامه جدید ایجاد شد",
  "program.approved": "برنامه تأیید شد",
  "program.duplicated": "برنامه کپی شد",
  "program.archived": "برنامه بایگانی شد",
  "pdf.generated": "PDF تولید شد",
  "photo.uploaded": "عکس پیشرفت ثبت شد",
  "measurement.created": "اندازه‌های بدن ثبت شد",
};

export function activityLabel(action: string): string {
  return activityLabels[action] ?? action;
}
