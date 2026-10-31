"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { AlertCircle, ClipboardList, Loader2, Pill, Salad, Search, Sparkles, X } from "lucide-react";
import { toast } from "sonner";

import { StudentAvatar } from "@/components/students/student-avatar";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiFetch } from "@/lib/api";
import { toPersianDigits } from "@/lib/format";
import { parseJalaliInput, toAsciiDigits } from "@/lib/jalali";
import { programTypeLabel } from "@/lib/labels";
import type { Program, ProgramType, Student, StudentListItem, StudentListResponse } from "@/lib/types";
import { useDebounced } from "@/lib/use-debounced";
import { cn } from "@/lib/utils";

const TYPES: { value: ProgramType; icon: typeof ClipboardList }[] = [
  { value: "workout", icon: ClipboardList },
  { value: "nutrition", icon: Salad },
  { value: "supplement", icon: Pill },
  { value: "vitamin", icon: Sparkles },
];

type Picked = { id: string; full_name: string; profile_photo_url: string | null };

function StudentPicker({ value, onChange }: { value: Picked | null; onChange: (s: Picked | null) => void }) {
  const [q, setQ] = useState("");
  const debounced = useDebounced(q, 250);
  const [results, setResults] = useState<StudentListItem[]>([]);

  useEffect(() => {
    if (value) return;
    let cancelled = false;
    const sp = new URLSearchParams({ status: "current", page_size: "8", sort: "name", order: "asc" });
    if (debounced.trim()) sp.set("q", debounced.trim());
    apiFetch<StudentListResponse>(`/api/students?${sp}`)
      .then((r) => !cancelled && setResults(r.items))
      .catch(() => !cancelled && setResults([]));
    return () => {
      cancelled = true;
    };
  }, [debounced, value]);

  if (value)
    return (
      <div className="flex items-center justify-between gap-3 rounded-lg border p-3">
        <span className="flex items-center gap-3 font-medium">
          <StudentAvatar name={value.full_name} photoUrl={value.profile_photo_url} />
          {value.full_name}
        </span>
        <Button type="button" variant="ghost" size="sm" onClick={() => onChange(null)}>
          <X aria-hidden />
          تغییر
        </Button>
      </div>
    );

  return (
    <div className="flex flex-col gap-2">
      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
        <Input id="student-search" value={q} onChange={(e) => setQ(e.target.value)} className="pr-9"
          placeholder="جستجوی شاگرد با نام یا موبایل" aria-label="جستجوی شاگرد" />
      </div>
      <ul className="divide-y rounded-lg border" role="listbox" aria-label="نتایج جستجوی شاگرد">
        {results.length === 0 && <li className="p-3 text-sm text-muted-foreground">شاگردی پیدا نشد.</li>}
        {results.map((s) => (
          <li key={s.id}>
            <button type="button" role="option" aria-selected={false}
              className="flex w-full cursor-pointer items-center gap-3 p-3 text-right hover:bg-muted/50"
              onClick={() => onChange({ id: s.id, full_name: s.full_name, profile_photo_url: s.profile_photo_url })}>
              <StudentAvatar name={s.full_name} photoUrl={s.profile_photo_url} />
              <span className="font-medium">{s.full_name}</span>
              {s.phone && <span className="ltr text-xs text-muted-foreground">{toPersianDigits(s.phone)}</span>}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Next.js reuses the hidden page for /programs/new with different query strings,
 * so remount the form whenever ?student= / ?type= change.
 */
export function NewProgramForm() {
  const params = useSearchParams();
  const studentParam = params.get("student");
  const typeParam = params.get("type") as ProgramType | null;
  return (
    <NewProgramFormInner key={`${studentParam ?? ""}:${typeParam ?? ""}`} studentParam={studentParam} typeParam={typeParam} />
  );
}

function NewProgramFormInner({ studentParam, typeParam }: { studentParam: string | null; typeParam: ProgramType | null }) {
  const router = useRouter();

  const [student, setStudent] = useState<Picked | null>(null);
  const [type, setType] = useState<ProgramType>(
    typeParam && typeParam in programTypeLabel ? typeParam : "workout",
  );
  const [period, setPeriod] = useState<string>("");
  const [title, setTitle] = useState("");
  const [titleTouched, setTitleTouched] = useState(false);
  const [startDate, setStartDate] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  // Preselected student from ?student=
  useEffect(() => {
    if (!studentParam) return;
    let cancelled = false;
    apiFetch<Student>(`/api/students/${studentParam}`)
      .then((s) => !cancelled && setStudent({ id: s.id, full_name: s.full_name, profile_photo_url: s.profile_photo_url }))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [studentParam]);

  // Suggest the next period number for this student + type
  useEffect(() => {
    if (!student) return;
    let cancelled = false;
    apiFetch<{ period_number: number }>(`/api/students/${student.id}/programs/next-period?type=${type}`)
      .then((r) => !cancelled && setPeriod(String(r.period_number)))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [student, type]);

  const suggestedTitle = `برنامه ${programTypeLabel[type]}${period ? ` دوره ${toPersianDigits(period)}` : ""}`;
  const effectiveTitle = titleTouched ? title : suggestedTitle;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!student) return setError("شاگرد را انتخاب کنید.");
    if (!effectiveTitle.trim()) return setError("عنوان الزامی است.");
    const start = parseJalaliInput(startDate);
    if (!start.ok) return setError("تاریخ شروع را به شکل ۱۴۰۵/۰۸/۰۹ وارد کنید.");
    const periodNum = toAsciiDigits(period).trim();
    setPending(true);
    try {
      const created = await apiFetch<Program>(`/api/students/${student.id}/programs`, {
        method: "POST",
        body: JSON.stringify({
          title: effectiveTitle.trim(),
          program_type: type,
          period_number: periodNum ? Number(periodNum) : null,
          start_date: start.iso,
        }),
      });
      toast.success("پیش‌نویس برنامه ساخته شد.");
      // This page stays mounted (hidden) after navigation — reset it
      setTitle("");
      setTitleTouched(false);
      setStartDate("");
      setPending(false);
      if (!studentParam) setStudent(null);
      setPeriod("");
      router.push(`/programs/${created.id}/edit`);
    } catch (err) {
      setError((err as Error).message);
      setPending(false);
    }
  }

  return (
    <form onSubmit={submit} noValidate className="flex max-w-3xl flex-col gap-6">
      {error && (
        <Alert variant="destructive">
          <AlertCircle aria-hidden />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <Card>
        <CardHeader><CardTitle>۱. شاگرد</CardTitle></CardHeader>
        <CardContent>
          <StudentPicker value={student} onChange={setStudent} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>۲. نوع برنامه</CardTitle></CardHeader>
        <CardContent>
          <div role="radiogroup" aria-label="نوع برنامه" className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {TYPES.map(({ value, icon: Icon }) => (
              <button key={value} type="button" role="radio" aria-checked={type === value} onClick={() => setType(value)}
                className={cn(
                  "flex cursor-pointer flex-col items-center gap-2 rounded-lg border p-4 text-sm font-medium transition-colors",
                  type === value ? "border-primary bg-accent text-accent-foreground ring-2 ring-primary/30" : "hover:bg-muted/50",
                )}>
                <Icon className="size-6" aria-hidden />
                {programTypeLabel[value]}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>۳. مشخصات</CardTitle></CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-3">
          <div className="flex flex-col gap-2 sm:col-span-3">
            <Label htmlFor="program-title">عنوان</Label>
            <Input id="program-title" value={effectiveTitle} maxLength={200}
              onChange={(e) => { setTitle(e.target.value); setTitleTouched(true); }} />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="program-period">شماره دوره</Label>
            <Input id="program-period" value={period} onChange={(e) => setPeriod(e.target.value)} inputMode="numeric" dir="ltr" />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="program-start">تاریخ شروع (اختیاری، مثل ۱۴۰۵/۰۸/۰۱)</Label>
            <Input id="program-start" value={startDate} onChange={(e) => setStartDate(e.target.value)}
              inputMode="numeric" dir="ltr" />
          </div>
        </CardContent>
      </Card>

      <div className="flex gap-2">
        <Button type="submit" size="lg" disabled={pending}>
          {pending && <Loader2 className="animate-spin" aria-hidden />}
          ساخت پیش‌نویس و ادامه
        </Button>
        <Button asChild variant="outline" size="lg">
          <Link href={studentParam ? `/students/${studentParam}?tab=programs` : "/programs"}>انصراف</Link>
        </Button>
      </div>
    </form>
  );
}
