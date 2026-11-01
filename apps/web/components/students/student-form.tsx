"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AlertCircle, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import { apiFetch } from "@/lib/api";
import { isoToJalaliInput, parseDecimalInput, parseJalaliInput, toAsciiDigits } from "@/lib/jalali";
import { genderLabel, studentStatusLabel } from "@/lib/labels";
import type { Gender, Student, StudentStatus } from "@/lib/types";
import { ProfilePhotoField, type PhotoChange } from "./profile-photo-field";

type Values = {
  first_name: string;
  last_name: string;
  phone: string;
  birth_date: string; // Jalali text
  gender: Gender | "";
  height_cm: string;
  initial_weight_kg: string;
  current_weight_kg: string;
  training_history: string;
  goal: string;
  limitations_notes: string;
  start_date: string; // Jalali text
  coach_notes: string;
  status: StudentStatus;
};

type Errors = Partial<Record<keyof Values, string>>;

function initialValues(s?: Student): Values {
  return {
    first_name: s?.first_name ?? "",
    last_name: s?.last_name ?? "",
    phone: s?.phone ?? "",
    birth_date: isoToJalaliInput(s?.birth_date),
    gender: s?.gender ?? "",
    height_cm: s?.height_cm ?? "",
    initial_weight_kg: s?.initial_weight_kg ?? "",
    current_weight_kg: s?.current_weight_kg ?? "",
    training_history: s?.training_history ?? "",
    goal: s?.goal ?? "",
    limitations_notes: s?.limitations_notes ?? "",
    start_date: isoToJalaliInput(s?.start_date),
    coach_notes: s?.coach_notes ?? "",
    status: s?.status ?? "active",
  };
}

const NUMBER_RANGES = {
  height_cm: [50, 260, "قد"],
  initial_weight_kg: [20, 400, "وزن اولیه"],
  current_weight_kg: [20, 400, "وزن فعلی"],
} as const;

/** Client-side validation + conversion to the API payload. Server re-validates everything. */
function toPayload(v: Values): { payload?: Record<string, unknown>; errors: Errors } {
  const errors: Errors = {};
  const payload: Record<string, unknown> = {};

  if (!v.first_name.trim()) errors.first_name = "نام الزامی است.";
  if (!v.last_name.trim()) errors.last_name = "نام خانوادگی الزامی است.";
  payload.first_name = v.first_name.trim();
  payload.last_name = v.last_name.trim();

  const phone = toAsciiDigits(v.phone).replace(/[\s-]/g, "");
  if (phone && !/^\+?\d{7,15}$/.test(phone)) errors.phone = "شماره موبایل معتبر نیست.";
  payload.phone = phone || null;

  for (const key of ["birth_date", "start_date"] as const) {
    const parsed = parseJalaliInput(v[key]);
    if (!parsed.ok) errors[key] = "تاریخ را به شکل ۱۴۰۵/۰۸/۰۹ وارد کنید.";
    else payload[key] = parsed.iso;
  }

  for (const [key, [min, max, label]] of Object.entries(NUMBER_RANGES) as [
    keyof typeof NUMBER_RANGES,
    (typeof NUMBER_RANGES)[keyof typeof NUMBER_RANGES],
  ][]) {
    const parsed = parseDecimalInput(v[key]);
    if (!parsed.ok) errors[key] = `${label} باید عدد باشد.`;
    else if (parsed.value !== null && (parsed.value < min || parsed.value > max))
      errors[key] = `${label} باید بین ${min.toLocaleString("fa-IR")} و ${max.toLocaleString("fa-IR")} باشد.`;
    else payload[key] = parsed.value === null ? null : Math.round(parsed.value * 10) / 10;
  }

  payload.gender = v.gender || null;
  for (const key of ["training_history", "goal", "limitations_notes", "coach_notes"] as const) {
    payload[key] = v[key].trim() || null;
  }
  payload.status = v.status;

  return Object.keys(errors).length ? { errors } : { payload, errors };
}

function Field({
  id,
  label,
  error,
  hint,
  required,
  children,
  className,
}: {
  id: string;
  label: string;
  error?: string;
  hint?: string;
  required?: boolean;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`flex flex-col gap-2 ${className ?? ""}`}>
      <Label htmlFor={id}>
        {label}
        {required && <span className="text-destructive" aria-hidden>*</span>}
      </Label>
      {children}
      {hint && !error && (
        <p id={`${id}-hint`} className="text-xs text-muted-foreground">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="text-xs text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}

export function StudentForm({ student }: { student?: Student }) {
  const router = useRouter();
  const isEdit = !!student;
  const [values, setValues] = useState<Values>(() => initialValues(student));
  const [errors, setErrors] = useState<Errors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [photo, setPhoto] = useState<PhotoChange>({ kind: "none" });
  const [photoError, setPhotoError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const set =
    (key: keyof Values) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
      setValues((v) => ({ ...v, [key]: e.target.value }));

  const inputProps = (key: keyof Values) => ({
    id: key,
    name: key,
    value: values[key],
    onChange: set(key),
    "aria-invalid": !!errors[key],
    "aria-describedby": errors[key] ? `${key}-error` : undefined,
  });

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    setPhotoError(null);
    const { payload, errors: errs } = toPayload(values);
    setErrors(errs);
    if (!payload) {
      setFormError("لطفاً خطاهای فرم را برطرف کنید.");
      return;
    }
    if (photo.kind === "upload" && !photo.consent && !student?.photo_consent_at) {
      setPhotoError("برای ثبت تصویر، رضایت شاگرد را تأیید کنید.");
      return;
    }

    setPending(true);
    let saved: Student;
    try {
      saved = isEdit
        ? await apiFetch<Student>(`/api/students/${student.id}`, { method: "PUT", body: JSON.stringify(payload) })
        : await apiFetch<Student>("/api/students", { method: "POST", body: JSON.stringify(payload) });
    } catch (err) {
      setFormError((err as Error).message);
      setPending(false);
      return;
    }

    try {
      if (photo.kind === "upload") {
        const fd = new FormData();
        fd.append("file", photo.file);
        fd.append("consent", String(photo.consent));
        await apiFetch(`/api/students/${saved.id}/profile-photo`, { method: "PUT", body: fd });
      } else if (photo.kind === "remove") {
        await apiFetch(`/api/students/${saved.id}/profile-photo`, { method: "DELETE" });
      }
    } catch (err) {
      toast.error(`اطلاعات ذخیره شد اما تصویر ثبت نشد: ${(err as Error).message}`);
      setPending(false);
      if (!isEdit) router.replace(`/students/${saved.id}/edit`);
      return;
    }

    toast.success(isEdit ? "تغییرات ذخیره شد." : "شاگرد جدید ثبت شد.");
    // Next.js keeps this page mounted but hidden (Activity) after navigation:
    // reset so "new student" starts empty and no button stays disabled.
    setPending(false);
    if (!isEdit) {
      setValues(initialValues());
      setPhoto({ kind: "none" });
      setErrors({});
    }
    router.push(`/students/${saved.id}`);
  }

  const fullName = `${values.first_name} ${values.last_name}`.trim();

  return (
    <form onSubmit={onSubmit} noValidate className="flex max-w-3xl flex-col gap-6">
      {formError && (
        <Alert variant="destructive">
          <AlertCircle aria-hidden />
          <AlertDescription>{formError}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle>مشخصات پایه</CardTitle>
          <CardDescription>فقط نام و نام خانوادگی الزامی است.</CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field id="first_name" label="نام" required error={errors.first_name}>
            <Input {...inputProps("first_name")} autoComplete="off" maxLength={100} required />
          </Field>
          <Field id="last_name" label="نام خانوادگی" required error={errors.last_name}>
            <Input {...inputProps("last_name")} autoComplete="off" maxLength={100} required />
          </Field>
          <Field id="phone" label="شماره موبایل" error={errors.phone}>
            <Input {...inputProps("phone")} inputMode="tel" dir="ltr" />
          </Field>
          <Field id="gender" label="جنسیت">
            <NativeSelect id="gender" value={values.gender} onChange={set("gender")}>
              <option value="">انتخاب نشده</option>
              {(Object.keys(genderLabel) as Gender[]).map((g) => (
                <option key={g} value={g}>
                  {genderLabel[g]}
                </option>
              ))}
            </NativeSelect>
          </Field>
          <Field id="birth_date" label="تاریخ تولد" error={errors.birth_date} hint="شمسی، مثل ۱۳۷۴/۰۲/۱۱">
            <Input {...inputProps("birth_date")} inputMode="numeric" dir="ltr" />
          </Field>
          <Field id="start_date" label="تاریخ شروع همکاری" error={errors.start_date} hint="شمسی، مثل ۱۴۰۵/۰۸/۰۱">
            <Input {...inputProps("start_date")} inputMode="numeric" dir="ltr" />
          </Field>
          {isEdit && (
            <Field id="status" label="وضعیت">
              <NativeSelect id="status" value={values.status} onChange={set("status")}>
                {(Object.keys(studentStatusLabel) as StudentStatus[]).map((s) => (
                  <option key={s} value={s}>
                    {studentStatusLabel[s]}
                  </option>
                ))}
              </NativeSelect>
            </Field>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>اطلاعات جسمی</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Field id="height_cm" label="قد (سانتی‌متر)" error={errors.height_cm}>
            <Input {...inputProps("height_cm")} inputMode="decimal" dir="ltr" />
          </Field>
          <Field id="initial_weight_kg" label="وزن اولیه (کیلوگرم)" error={errors.initial_weight_kg}>
            <Input {...inputProps("initial_weight_kg")} inputMode="decimal" dir="ltr" />
          </Field>
          <Field id="current_weight_kg" label="وزن فعلی (کیلوگرم)" error={errors.current_weight_kg}>
            <Input {...inputProps("current_weight_kg")} inputMode="decimal" dir="ltr" />
          </Field>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>سابقه و هدف</CardTitle>
          <CardDescription>اطلاعات جسمی و حساس را فقط در حد نیاز و با اطلاع شاگرد ثبت کنید.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          <Field id="training_history" label="سابقه تمرینی">
            <Textarea {...inputProps("training_history")} rows={3} maxLength={5000} />
          </Field>
          <Field id="goal" label="هدف تمرینی">
            <Textarea {...inputProps("goal")} rows={3} maxLength={5000} />
          </Field>
          <Field id="limitations_notes" label="محدودیت‌ها یا آسیب‌های اعلام‌شده">
            <Textarea {...inputProps("limitations_notes")} rows={3} maxLength={5000} />
          </Field>
          <Field id="coach_notes" label="توضیحات مربی">
            <Textarea {...inputProps("coach_notes")} rows={3} maxLength={5000} />
          </Field>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>تصویر پروفایل</CardTitle>
          <CardDescription>اختیاری. تصویر خصوصی نگهداری می‌شود و اطلاعات مکان (EXIF) از آن حذف می‌شود.</CardDescription>
        </CardHeader>
        <CardContent>
          <ProfilePhotoField
            name={fullName}
            currentUrl={student?.profile_photo_url ?? null}
            consentRecorded={!!student?.photo_consent_at}
            value={photo}
            onChange={(v) => {
              setPhoto(v);
              setPhotoError(null);
            }}
            error={photoError}
          />
        </CardContent>
      </Card>

      <div className="flex flex-wrap gap-2">
        <Button type="submit" size="lg" disabled={pending}>
          {pending && <Loader2 className="animate-spin" aria-hidden />}
          {isEdit ? "ذخیره تغییرات" : "ثبت شاگرد"}
        </Button>
        <Button asChild type="button" variant="outline" size="lg">
          <Link href={isEdit ? `/students/${student.id}` : "/students"}>انصراف</Link>
        </Button>
      </div>
    </form>
  );
}
