"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { AlertCircle, ChevronLeft, ChevronRight, ClipboardList, FileText, Plus, Search } from "lucide-react";

import { PageHeader } from "@/components/layout/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch } from "@/lib/api";
import { formatJalaliDate, toPersianDigits } from "@/lib/format";
import { programTypeLabel } from "@/lib/labels";
import type { ProgramListResponse, ProgramType } from "@/lib/types";
import { useDebounced } from "@/lib/use-debounced";
import { ProgramStatusBadge } from "./program-status-badge";

const PAGE_SIZE = 20;
const STATUS_OPTIONS = [
  { value: "current", label: "پیش‌نویس و تأییدشده" },
  { value: "draft", label: "فقط پیش‌نویس" },
  { value: "approved", label: "فقط تأییدشده" },
  { value: "archived", label: "بایگانی‌شده" },
  { value: "all", label: "همه" },
];

export function ProgramsList() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const q = params.get("q") ?? "";
  const status = params.get("status") ?? "current";
  const type = params.get("type") ?? "";
  const page = Math.max(1, Number(params.get("page") ?? "1") || 1);

  const [search, setSearch] = useState(q);
  const debounced = useDebounced(search, 350);
  const [data, setData] = useState<ProgramListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  function updateParams(next: Record<string, string | null>) {
    const sp = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(next)) {
      if (!v) sp.delete(k);
      else sp.set(k, v);
    }
    const qs = sp.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }

  useEffect(() => {
    if (debounced.trim() !== q) updateParams({ q: debounced.trim() || null, page: null });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced]);

  useEffect(() => {
    let cancelled = false;
    const sp = new URLSearchParams({ status, page: String(page), page_size: String(PAGE_SIZE) });
    if (q) sp.set("q", q);
    if (type) sp.set("type", type);
    apiFetch<ProgramListResponse>(`/api/programs?${sp}`)
      .then((d) => {
        if (cancelled) return;
        setError(null);
        setData(d);
      })
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [q, status, type, page]);

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <>
      <PageHeader
        title="برنامه‌ها"
        description={data ? `${toPersianDigits(data.total)} برنامه` : undefined}
        actions={
          <Button asChild>
            <Link href="/programs/new">
              <Plus aria-hidden />
              ثبت برنامه جدید
            </Link>
          </Button>
        }
      />
      <div className="mb-4 grid gap-3 sm:grid-cols-[1fr_auto_auto]">
        <div className="relative">
          <Search className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input type="search" value={search} onChange={(e) => setSearch(e.target.value)} className="pr-9"
            placeholder="جستجو با عنوان یا نام شاگرد" aria-label="جستجوی برنامه" />
        </div>
        <NativeSelect aria-label="نوع برنامه" value={type} onChange={(e) => updateParams({ type: e.target.value, page: null })}>
          <option value="">همه انواع</option>
          {(Object.keys(programTypeLabel) as ProgramType[]).map((t) => (
            <option key={t} value={t}>{programTypeLabel[t]}</option>
          ))}
        </NativeSelect>
        <NativeSelect aria-label="وضعیت" value={status}
          onChange={(e) => updateParams({ status: e.target.value === "current" ? null : e.target.value, page: null })}>
          {STATUS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </NativeSelect>
      </div>

      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertCircle aria-hidden />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {!data && !error && <Skeleton className="h-40 w-full" />}
      {data && data.items.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-12 text-center text-muted-foreground">
            <ClipboardList className="size-8" aria-hidden />
            <p>{q || type || status !== "current" ? "برنامه‌ای با این مشخصات پیدا نشد." : "هنوز برنامه‌ای ثبت نشده است."}</p>
          </CardContent>
        </Card>
      )}
      {data && data.items.length > 0 && (
        <ul className="flex flex-col gap-2">
          {data.items.map((p) => (
            <li key={p.id}>
              <Link href={`/programs/${p.id}`}
                className="flex flex-col gap-2 rounded-xl border bg-card p-4 shadow-xs transition-colors hover:bg-muted/30 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <p className="truncate font-medium">{p.title}</p>
                  <p className="text-xs text-muted-foreground">
                    {p.student.full_name} · {programTypeLabel[p.program_type]}
                    {p.period_number ? ` · دوره ${toPersianDigits(p.period_number)}` : ""} · آخرین تغییر{" "}
                    {formatJalaliDate(p.updated_at)}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  {p.pdf_count > 0 && (
                    <span className="flex items-center gap-1 text-xs text-muted-foreground">
                      <FileText className="size-3.5" aria-hidden />
                      {toPersianDigits(p.pdf_count)} PDF
                    </span>
                  )}
                  <ProgramStatusBadge status={p.status} />
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
      {data && totalPages > 1 && (
        <nav aria-label="صفحه‌بندی" className="mt-4 flex items-center justify-center gap-3">
          <Button variant="outline" size="sm" disabled={page <= 1}
            onClick={() => updateParams({ page: page - 1 > 1 ? String(page - 1) : null })}>
            <ChevronRight aria-hidden />
            قبلی
          </Button>
          <span className="text-sm text-muted-foreground">
            صفحه {toPersianDigits(page)} از {toPersianDigits(totalPages)}
          </span>
          <Button variant="outline" size="sm" disabled={page >= totalPages}
            onClick={() => updateParams({ page: String(page + 1) })}>
            بعدی
            <ChevronLeft aria-hidden />
          </Button>
        </nav>
      )}
    </>
  );
}
