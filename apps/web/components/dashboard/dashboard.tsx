"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Activity as ActivityIcon,
  AlertCircle,
  CalendarCheck,
  ClipboardList,
  Plus,
  Search,
  UserCheck,
  Users,
  type LucideIcon,
} from "lucide-react";

import { PageHeader } from "@/components/layout/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch } from "@/lib/api";
import { formatJalaliDate, formatNumber } from "@/lib/format";
import { activityLabel, programStatusLabel, programTypeLabel, studentStatusLabel } from "@/lib/labels";
import type { Activity, DashboardSummary } from "@/lib/types";

function StatCard({ label, value, icon: Icon }: { label: string; value: number | undefined; icon: LucideIcon }) {
  return (
    <Card className="gap-3">
      <CardContent className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm text-muted-foreground">{label}</p>
          {value === undefined ? (
            <Skeleton className="mt-2 h-8 w-12" />
          ) : (
            <p className="mt-1 text-3xl font-bold">{formatNumber(value, 0)}</p>
          )}
        </div>
        <span className="hidden size-11 shrink-0 items-center justify-center rounded-xl bg-accent text-accent-foreground sm:flex">
          <Icon className="size-5" aria-hidden />
        </span>
      </CardContent>
    </Card>
  );
}

function QuickSearch() {
  const router = useRouter();
  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const q = String(new FormData(e.currentTarget).get("q") ?? "").trim();
    router.push(q ? `/students?q=${encodeURIComponent(q)}` : "/students");
  }
  return (
    <form onSubmit={onSubmit} role="search" className="relative w-full sm:max-w-sm">
      <Search className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
      <Input name="q" placeholder="جستجوی شاگرد با نام یا موبایل" className="pr-9" aria-label="جستجوی سریع شاگرد" />
    </form>
  );
}

function ListSkeleton() {
  return (
    <div className="flex flex-col gap-3">
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="py-6 text-center text-sm text-muted-foreground">{children}</p>;
}

function Pill({ children }: { children: React.ReactNode }) {
  return <span className="rounded-full border px-2 py-0.5 text-xs text-muted-foreground">{children}</span>;
}

export function Dashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [activity, setActivity] = useState<Activity[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      apiFetch<DashboardSummary>("/api/dashboard/summary"),
      apiFetch<Activity[]>("/api/dashboard/recent-activity?limit=8"),
    ])
      .then(([s, a]) => {
        setSummary(s);
        setActivity(a);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <>
      <PageHeader
        title="داشبورد"
        actions={
          <>
            <Button asChild>
              <Link href="/students/new">
                <Plus aria-hidden />
                افزودن شاگرد
              </Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/programs/new">
                <ClipboardList aria-hidden />
                ثبت برنامه جدید
              </Link>
            </Button>
          </>
        }
      />

      {error && (
        <Alert variant="destructive" className="mb-6">
          <AlertCircle aria-hidden />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="mb-6">
        <QuickSearch />
      </div>

      <section aria-label="آمار" className="mb-6 grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard label="کل شاگردان" value={summary?.total_students} icon={Users} />
        <StatCard label="شاگردان فعال" value={summary?.active_students} icon={UserCheck} />
        <StatCard label="کل برنامه‌های ثبت‌شده" value={summary?.total_programs} icon={ClipboardList} />
        <StatCard label="برنامه‌های این ماه" value={summary?.programs_this_month} icon={CalendarCheck} />
      </section>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>آخرین شاگردان</CardTitle>
          </CardHeader>
          <CardContent>
            {!summary ? (
              <ListSkeleton />
            ) : summary.recent_students.length === 0 ? (
              <Empty>هنوز شاگردی ثبت نشده است.</Empty>
            ) : (
              <ul className="divide-y">
                {summary.recent_students.map((s) => (
                  <li key={s.id} className="flex items-center justify-between gap-3 py-3">
                    <div className="min-w-0">
                      <Link href={`/students/${s.id}`} className="block truncate font-medium hover:underline">
                        {s.full_name}
                      </Link>
                      <p className="text-xs text-muted-foreground">
                        شروع: {formatJalaliDate(s.start_date)}
                      </p>
                    </div>
                    <Pill>{studentStatusLabel[s.status]}</Pill>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>آخرین برنامه‌ها</CardTitle>
          </CardHeader>
          <CardContent>
            {!summary ? (
              <ListSkeleton />
            ) : summary.recent_programs.length === 0 ? (
              <Empty>هنوز برنامه‌ای ثبت نشده است.</Empty>
            ) : (
              <ul className="divide-y">
                {summary.recent_programs.map((p) => (
                  <li key={p.id} className="flex items-center justify-between gap-3 py-3">
                    <div className="min-w-0">
                      <Link href={`/programs/${p.id}`} className="block truncate font-medium hover:underline">
                        {p.title}
                      </Link>
                      <p className="truncate text-xs text-muted-foreground">
                        {p.student_name} · {programTypeLabel[p.program_type]} ·{" "}
                        {formatJalaliDate(p.approved_at ?? p.created_at)}
                      </p>
                    </div>
                    <Pill>{programStatusLabel[p.status]}</Pill>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ActivityIcon className="size-4" aria-hidden />
              فعالیت‌های اخیر
            </CardTitle>
          </CardHeader>
          <CardContent>
            {!activity ? (
              <ListSkeleton />
            ) : activity.length === 0 ? (
              <Empty>فعالیتی ثبت نشده است.</Empty>
            ) : (
              <ul className="divide-y">
                {activity.map((a) => (
                  <li key={a.id} className="py-3">
                    <p className="text-sm">
                      {activityLabel(a.action)}
                      {a.student_name && <span className="text-muted-foreground"> — {a.student_name}</span>}
                    </p>
                    <p className="text-xs text-muted-foreground">{formatJalaliDate(a.created_at)}</p>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
