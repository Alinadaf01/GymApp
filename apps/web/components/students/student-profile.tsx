"use client";

import Link from "next/link";
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import {
  AlertCircle,
  ArrowRight,
  ClipboardList,
  History,
  Images,
  LineChart,
  Loader2,
  Pencil,
  Plus,
  UserRound,
} from "lucide-react";

import { ComingSoon } from "@/components/layout/coming-soon";
import { ProgramStatusBadge } from "@/components/programs/program-status-badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { apiFetch } from "@/lib/api";
import { formatJalaliDate, formatNumber, toPersianDigits } from "@/lib/format";
import { activityLabel, genderLabel, programTypeLabel, studentFieldLabel } from "@/lib/labels";
import type { Activity, ProgramSummary, Student } from "@/lib/types";
import { ArchiveButton } from "./archive-button";
import { StudentAvatar } from "./student-avatar";
import { StudentStatusBadge } from "./student-status-badge";
import { useStudent } from "./use-student";

const TABS = ["overview", "programs", "photos", "trends", "history"] as const;
type Tab = (typeof TABS)[number];

function Dash() {
  return <span className="text-muted-foreground">—</span>;
}

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 truncate font-medium">{children}</dd>
    </div>
  );
}

function measure(value: string | null, unit: string) {
  return value ? `${formatNumber(value)} ${unit}` : <Dash />;
}

function ProfileHeader({ student, onChanged }: { student: Student; onChanged: (s: Student) => void }) {
  return (
    <Card className="mb-6">
      <CardContent className="flex flex-col gap-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-center gap-4">
            <StudentAvatar name={student.full_name} photoUrl={student.profile_photo_url} size="lg" />
            <div className="min-w-0">
              <h1 className="text-2xl font-bold">{student.full_name}</h1>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <StudentStatusBadge status={student.status} />
                {student.archived_at && (
                  <span className="text-xs text-muted-foreground">
                    بایگانی در {formatJalaliDate(student.archived_at)}
                  </span>
                )}
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button asChild>
              <Link href={`/students/${student.id}/edit`}>
                <Pencil aria-hidden />
                ویرایش
              </Link>
            </Button>
            <ArchiveButton student={student} onChanged={onChanged} />
          </div>
        </div>
        <dl className="grid grid-cols-2 gap-4 border-t pt-4 text-sm sm:grid-cols-3 lg:grid-cols-6">
          <Fact label="موبایل">
            {student.phone ? <span className="ltr">{toPersianDigits(student.phone)}</span> : <Dash />}
          </Fact>
          <Fact label="قد">{measure(student.height_cm, "سانتی‌متر")}</Fact>
          <Fact label="وزن فعلی">{measure(student.current_weight_kg, "کیلوگرم")}</Fact>
          <Fact label="شروع همکاری">{formatJalaliDate(student.start_date)}</Fact>
          <Fact label="آخرین برنامه">
            {student.last_program ? (
              <span title={student.last_program.title}>
                {student.last_program.title} ({formatJalaliDate(student.last_program.date)})
              </span>
            ) : (
              <Dash />
            )}
          </Fact>
          <Fact label="عضویت در پنل">{formatJalaliDate(student.created_at)}</Fact>
        </dl>
      </CardContent>
    </Card>
  );
}

function TextBlock({ title, text }: { title: string; text: string | null }) {
  return (
    <div>
      <h3 className="mb-1 text-sm font-semibold">{title}</h3>
      {text ? (
        <p className="text-sm leading-7 whitespace-pre-line">{text}</p>
      ) : (
        <p className="text-sm text-muted-foreground">ثبت نشده</p>
      )}
    </div>
  );
}

function ActivityList({ items }: { items: Activity[] }) {
  if (items.length === 0) return <p className="py-4 text-sm text-muted-foreground">فعالیتی ثبت نشده است.</p>;
  return (
    <ol className="relative flex flex-col gap-4 border-r pr-4">
      {items.map((a) => {
        const fields = Array.isArray(a.meta?.fields) ? (a.meta.fields as string[]) : [];
        return (
          <li key={a.id} className="relative">
            <span className="absolute top-1.5 -right-[21px] size-2.5 rounded-full border-2 border-card bg-primary" aria-hidden />
            <p className="text-sm font-medium">{activityLabel(a.action)}</p>
            {fields.length > 0 && (
              <p className="text-xs text-muted-foreground">
                تغییر در: {fields.map((f) => studentFieldLabel[f] ?? f).join("، ")}
              </p>
            )}
            <p className="text-xs text-muted-foreground">{formatJalaliDate(a.created_at)}</p>
          </li>
        );
      })}
    </ol>
  );
}

function Overview({ student, activity }: { student: Student; activity: Activity[] | null }) {
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>مشخصات</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-5">
          <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
            <Fact label="تاریخ تولد">{formatJalaliDate(student.birth_date)}</Fact>
            <Fact label="جنسیت">{student.gender ? genderLabel[student.gender] : <Dash />}</Fact>
            <Fact label="وزن اولیه">{measure(student.initial_weight_kg, "کیلوگرم")}</Fact>
          </dl>
          <TextBlock title="سابقه تمرینی" text={student.training_history} />
          <TextBlock title="هدف تمرینی" text={student.goal} />
          <TextBlock title="محدودیت‌ها یا آسیب‌های اعلام‌شده" text={student.limitations_notes} />
          <TextBlock title="توضیحات مربی" text={student.coach_notes} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>آخرین تغییرات</CardTitle>
        </CardHeader>
        <CardContent>
          {activity ? <ActivityList items={activity.slice(0, 5)} /> : <Skeleton className="h-24 w-full" />}
        </CardContent>
      </Card>
    </div>
  );
}

function Programs({ studentId, archived }: { studentId: string; archived: boolean }) {
  const [programs, setPrograms] = useState<ProgramSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    apiFetch<ProgramSummary[]>(`/api/students/${studentId}/programs`)
      .then((p) => !cancelled && setPrograms(p))
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [studentId]);

  if (error)
    return (
      <Alert variant="destructive">
        <AlertCircle aria-hidden />
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  if (!programs) return <Skeleton className="h-24 w-full" />;
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle>برنامه‌ها</CardTitle>
        {!archived && (
          <Button asChild size="sm">
            <Link href={`/programs/new?student=${studentId}`}>
              <Plus aria-hidden />
              برنامه جدید
            </Link>
          </Button>
        )}
      </CardHeader>
      <CardContent>
        {programs.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">هنوز برنامه‌ای برای این شاگرد ثبت نشده است.</p>
        ) : (
          <ul className="divide-y">
            {programs.map((p) => (
              <li key={p.id}>
                <Link href={`/programs/${p.id}`} className="flex items-center justify-between gap-3 py-3 hover:bg-muted/30">
                  <div className="min-w-0">
                    <p className="truncate font-medium">{p.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {programTypeLabel[p.program_type]}
                      {p.period_number ? ` · دوره ${toPersianDigits(p.period_number)}` : ""} ·{" "}
                      {formatJalaliDate(p.approved_at ?? p.created_at)}
                    </p>
                  </div>
                  <ProgramStatusBadge status={p.status} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

export function StudentProfile() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const tabParam = params.get("tab");
  const tab: Tab = TABS.includes(tabParam as Tab) ? (tabParam as Tab) : "overview";

  const { student, setStudent, error } = useStudent(id);
  const [activity, setActivity] = useState<Activity[] | null>(null);

  useEffect(() => {
    if (!student) return;
    apiFetch<Activity[]>(`/api/students/${id}/activity`)
      .then(setActivity)
      .catch(() => setActivity([]));
  }, [id, student]);

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertCircle aria-hidden />
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }
  if (!student) {
    return (
      <div className="flex justify-center py-24 text-muted-foreground" role="status">
        <Loader2 className="size-6 animate-spin" aria-hidden />
        <span className="sr-only">در حال بارگذاری</span>
      </div>
    );
  }

  return (
    <>
      <Link href="/students" className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:underline">
        <ArrowRight className="size-4" aria-hidden />
        بازگشت به شاگردان
      </Link>
      <ProfileHeader student={student} onChanged={setStudent} />
      <Tabs
        value={tab}
        onValueChange={(v) => router.replace(v === "overview" ? pathname : `${pathname}?tab=${v}`, { scroll: false })}
      >
        <TabsList>
          <TabsTrigger value="overview">
            <UserRound aria-hidden />
            نمای کلی
          </TabsTrigger>
          <TabsTrigger value="programs">
            <ClipboardList aria-hidden />
            برنامه‌ها
          </TabsTrigger>
          <TabsTrigger value="photos">
            <Images aria-hidden />
            تصاویر پیشرفت
          </TabsTrigger>
          <TabsTrigger value="trends">
            <LineChart aria-hidden />
            روند تغییرات
          </TabsTrigger>
          <TabsTrigger value="history">
            <History aria-hidden />
            تاریخچه
          </TabsTrigger>
        </TabsList>
        <TabsContent value="overview">
          <Overview student={student} activity={activity} />
        </TabsContent>
        <TabsContent value="programs">
          <Programs studentId={student.id} archived={student.status === "archived"} />
        </TabsContent>
        <TabsContent value="photos">
          <ComingSoon phase={6} />
        </TabsContent>
        <TabsContent value="trends">
          <ComingSoon phase={6} />
        </TabsContent>
        <TabsContent value="history">
          <Card>
            <CardContent>
              {activity ? <ActivityList items={activity} /> : <Skeleton className="h-24 w-full" />}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </>
  );
}
