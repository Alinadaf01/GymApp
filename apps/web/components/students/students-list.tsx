"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { AlertCircle, ChevronLeft, ChevronRight, Eye, Pencil, Plus, Search, Users } from "lucide-react";

import { PageHeader } from "@/components/layout/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch } from "@/lib/api";
import { formatJalaliDate, formatNumber, toPersianDigits } from "@/lib/format";
import { programTypeLabel } from "@/lib/labels";
import type { StudentListItem, StudentListResponse } from "@/lib/types";
import { useDebounced } from "@/lib/use-debounced";
import { StudentAvatar } from "./student-avatar";
import { StudentStatusBadge } from "./student-status-badge";

const PAGE_SIZE = 20;

const SORT_OPTIONS = [
  { value: "created_at:desc", label: "جدیدترین ثبت" },
  { value: "created_at:asc", label: "قدیمی‌ترین ثبت" },
  { value: "name:asc", label: "نام خانوادگی (الف تا ی)" },
  { value: "name:desc", label: "نام خانوادگی (ی تا الف)" },
  { value: "start_date:desc", label: "تاریخ شروع (جدیدترین)" },
  { value: "start_date:asc", label: "تاریخ شروع (قدیمی‌ترین)" },
  { value: "current_weight:desc", label: "وزن فعلی (بیشترین)" },
  { value: "current_weight:asc", label: "وزن فعلی (کمترین)" },
];

const STATUS_OPTIONS = [
  { value: "current", label: "فعال و غیرفعال" },
  { value: "active", label: "فقط فعال" },
  { value: "inactive", label: "فقط غیرفعال" },
  { value: "archived", label: "بایگانی‌شده" },
  { value: "all", label: "همه" },
];

function LastProgramCell({ s }: { s: StudentListItem }) {
  if (!s.last_program) return <span className="text-muted-foreground">—</span>;
  return (
    <span className="block min-w-0">
      <span className="block truncate">{s.last_program.title}</span>
      <span className="text-xs text-muted-foreground">
        {programTypeLabel[s.last_program.program_type]} · {formatJalaliDate(s.last_program.date)}
      </span>
    </span>
  );
}

function Weight({ value }: { value: string | null }) {
  return value ? <>{formatNumber(value)} کیلوگرم</> : <span className="text-muted-foreground">—</span>;
}

export function StudentsList() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const q = params.get("q") ?? "";
  const status = params.get("status") ?? "current";
  const sort = params.get("sort") ?? "created_at:desc";
  const page = Math.max(1, Number(params.get("page") ?? "1") || 1);

  const [search, setSearch] = useState(q);
  const debouncedSearch = useDebounced(search, 350);
  const [data, setData] = useState<StudentListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  function updateParams(next: Record<string, string | null>) {
    const sp = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(next)) {
      if (v === null || v === "") sp.delete(k);
      else sp.set(k, v);
    }
    const qs = sp.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }

  // Search box -> URL (debounced), resetting to page 1
  useEffect(() => {
    if (debouncedSearch.trim() !== q) updateParams({ q: debouncedSearch.trim() || null, page: null });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedSearch]);

  useEffect(() => {
    let cancelled = false;
    const [sortField, order] = sort.split(":");
    const sp = new URLSearchParams({
      status,
      sort: sortField,
      order: order ?? "desc",
      page: String(page),
      page_size: String(PAGE_SIZE),
    });
    if (q) sp.set("q", q);
    apiFetch<StudentListResponse>(`/api/students?${sp}`)
      .then((d) => {
        if (cancelled) return;
        setError(null);
        setData(d);
      })
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [q, status, sort, page]);

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;
  const loading = !data && !error;

  return (
    <>
      <PageHeader
        title="شاگردان"
        description={data ? `${toPersianDigits(data.total)} شاگرد` : undefined}
        actions={
          <Button asChild>
            <Link href="/students/new">
              <Plus aria-hidden />
              افزودن شاگرد
            </Link>
          </Button>
        }
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-[1fr_auto_auto]">
        <div className="relative">
          <Search
            className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <Input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="جستجو با نام یا موبایل"
            aria-label="جستجوی شاگرد"
            className="pr-9"
          />
        </div>
        <NativeSelect
          aria-label="فیلتر وضعیت"
          value={status}
          onChange={(e) => updateParams({ status: e.target.value === "current" ? null : e.target.value, page: null })}
        >
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </NativeSelect>
        <NativeSelect
          aria-label="مرتب‌سازی"
          value={sort}
          onChange={(e) =>
            updateParams({ sort: e.target.value === "created_at:desc" ? null : e.target.value, page: null })
          }
        >
          {SORT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </NativeSelect>
      </div>

      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertCircle aria-hidden />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading && (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      )}

      {data && data.items.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-12 text-center text-muted-foreground">
            <Users className="size-8" aria-hidden />
            {q || status !== "current" ? (
              <p>شاگردی با این مشخصات پیدا نشد.</p>
            ) : (
              <>
                <p>هنوز شاگردی ثبت نشده است.</p>
                <Button asChild size="sm">
                  <Link href="/students/new">افزودن اولین شاگرد</Link>
                </Button>
              </>
            )}
          </CardContent>
        </Card>
      )}

      {data && data.items.length > 0 && (
        <>
          {/* Desktop table */}
          <Card className="hidden overflow-hidden py-0 md:flex">
            <table className="w-full text-sm">
              <thead className="border-b bg-muted/50 text-right text-xs text-muted-foreground">
                <tr>
                  <th scope="col" className="px-4 py-3 font-medium">نام</th>
                  <th scope="col" className="px-4 py-3 font-medium">موبایل</th>
                  <th scope="col" className="px-4 py-3 font-medium">وزن فعلی</th>
                  <th scope="col" className="px-4 py-3 font-medium">شروع همکاری</th>
                  <th scope="col" className="px-4 py-3 font-medium">آخرین برنامه</th>
                  <th scope="col" className="px-4 py-3 font-medium">وضعیت</th>
                  <th scope="col" className="px-4 py-3 font-medium">
                    <span className="sr-only">عملیات</span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {data.items.map((s) => (
                  <tr key={s.id} className="hover:bg-muted/30">
                    <td className="px-4 py-3">
                      <Link href={`/students/${s.id}`} className="flex items-center gap-3 font-medium hover:underline">
                        <StudentAvatar name={s.full_name} photoUrl={s.profile_photo_url} />
                        {s.full_name}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      {s.phone ? <span className="ltr">{toPersianDigits(s.phone)}</span> : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <Weight value={s.current_weight_kg} />
                    </td>
                    <td className="px-4 py-3">{formatJalaliDate(s.start_date)}</td>
                    <td className="max-w-48 px-4 py-3">
                      <LastProgramCell s={s} />
                    </td>
                    <td className="px-4 py-3">
                      <StudentStatusBadge status={s.status} />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-1">
                        <Button asChild variant="ghost" size="icon" aria-label={`مشاهده پرونده ${s.full_name}`}>
                          <Link href={`/students/${s.id}`}>
                            <Eye />
                          </Link>
                        </Button>
                        <Button asChild variant="ghost" size="icon" aria-label={`ویرایش ${s.full_name}`}>
                          <Link href={`/students/${s.id}/edit`}>
                            <Pencil />
                          </Link>
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          {/* Mobile cards */}
          <ul className="flex flex-col gap-3 md:hidden">
            {data.items.map((s) => (
              <li key={s.id}>
                <Card className="gap-3 py-4">
                  <CardContent className="flex flex-col gap-3 px-4">
                    <div className="flex items-center justify-between gap-3">
                      <Link href={`/students/${s.id}`} className="flex min-w-0 items-center gap-3">
                        <StudentAvatar name={s.full_name} photoUrl={s.profile_photo_url} />
                        <span className="min-w-0">
                          <span className="block truncate font-medium">{s.full_name}</span>
                          {s.phone && (
                            <span className="ltr block text-xs text-muted-foreground">{toPersianDigits(s.phone)}</span>
                          )}
                        </span>
                      </Link>
                      <StudentStatusBadge status={s.status} />
                    </div>
                    <dl className="grid grid-cols-2 gap-2 text-xs">
                      <div>
                        <dt className="text-muted-foreground">وزن فعلی</dt>
                        <dd><Weight value={s.current_weight_kg} /></dd>
                      </div>
                      <div>
                        <dt className="text-muted-foreground">شروع همکاری</dt>
                        <dd>{formatJalaliDate(s.start_date)}</dd>
                      </div>
                      <div className="col-span-2">
                        <dt className="text-muted-foreground">آخرین برنامه</dt>
                        <dd><LastProgramCell s={s} /></dd>
                      </div>
                    </dl>
                    <div className="flex gap-2">
                      <Button asChild variant="outline" size="sm" className="flex-1">
                        <Link href={`/students/${s.id}`}>مشاهده پرونده</Link>
                      </Button>
                      <Button asChild variant="ghost" size="sm">
                        <Link href={`/students/${s.id}/edit`}>ویرایش</Link>
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </li>
            ))}
          </ul>

          {totalPages > 1 && (
            <nav aria-label="صفحه‌بندی" className="mt-4 flex items-center justify-center gap-3">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => updateParams({ page: page - 1 > 1 ? String(page - 1) : null })}
              >
                <ChevronRight aria-hidden />
                قبلی
              </Button>
              <span className="text-sm text-muted-foreground">
                صفحه {toPersianDigits(page)} از {toPersianDigits(totalPages)}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => updateParams({ page: String(page + 1) })}
              >
                بعدی
                <ChevronLeft aria-hidden />
              </Button>
            </nav>
          )}
        </>
      )}
    </>
  );
}
