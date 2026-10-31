"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import {
  AlertCircle,
  Archive,
  ArrowRight,
  CircleCheck,
  Copy,
  FilePlus2,
  Loader2,
  Mic,
  Pencil,
  Trash2,
  TriangleAlert,
} from "lucide-react";
import { toast } from "sonner";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmButton } from "@/components/ui/confirm-button";
import { apiFetch } from "@/lib/api";
import { formatJalaliDate, toPersianDigits } from "@/lib/format";
import { programTypeLabel } from "@/lib/labels";
import type { PdfInfo, Program } from "@/lib/types";
import { PdfList } from "./pdf-list";
import { ProgramContentView } from "./program-content-view";
import { ProgramStatusBadge } from "./program-status-badge";
import { useProgram } from "./use-program";

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 font-medium">{children}</dd>
    </div>
  );
}

export function ProgramView() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { program, setProgram, error } = useProgram(id);
  const [busy, setBusy] = useState<string | null>(null);
  const [pdfKey, setPdfKey] = useState("0");

  async function run<T>(label: string, fn: () => Promise<T>): Promise<T | undefined> {
    setBusy(label);
    try {
      return await fn();
    } catch (e) {
      toast.error((e as Error).message);
      return undefined;
    } finally {
      setBusy(null);
    }
  }

  async function makePdf(p: Program) {
    const pdf = await apiFetch<PdfInfo>(`/api/programs/${p.id}/generate-pdf`, { method: "POST" });
    setProgram({ ...p, latest_pdf: pdf });
    setPdfKey(pdf.id);
    toast.success(`PDF نسخه ${toPersianDigits(pdf.version)} ساخته شد.`);
  }

  const approve = () =>
    run("approve", async () => {
      const approved = await apiFetch<Program>(`/api/programs/${id}/approve`, { method: "POST" });
      setProgram(approved);
      toast.success("برنامه تأیید شد.");
      try {
        await makePdf(approved);
      } catch (e) {
        toast.error(`برنامه تأیید شد اما ساخت PDF ناموفق بود: ${(e as Error).message}`);
      }
    });

  const generate = () => run("pdf", () => makePdf(program!));

  const duplicate = () =>
    run("copy", async () => {
      const copy = await apiFetch<Program>(`/api/programs/${id}/duplicate`, { method: "POST" });
      toast.success("کپی برنامه به‌عنوان پیش‌نویس ساخته شد.");
      router.push(`/programs/${copy.id}/edit`);
    });

  const archive = () =>
    run("archive", async () => {
      setProgram(await apiFetch<Program>(`/api/programs/${id}/archive`, { method: "POST" }));
      toast.success("برنامه بایگانی شد.");
    });

  const remove = () =>
    run("delete", async () => {
      await apiFetch(`/api/programs/${id}`, { method: "DELETE" });
      toast.success("پیش‌نویس حذف شد.");
      router.replace(`/students/${program!.student.id}?tab=programs`);
    });

  if (error)
    return (
      <Alert variant="destructive">
        <AlertCircle aria-hidden />
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  if (!program)
    return (
      <div className="flex justify-center py-24 text-muted-foreground" role="status">
        <Loader2 className="size-6 animate-spin" aria-hidden />
        <span className="sr-only">در حال بارگذاری</span>
      </div>
    );

  const spinner = (label: string) => busy === label && <Loader2 className="animate-spin" aria-hidden />;
  const pdfOutdated = program.status !== "draft" && (!program.latest_pdf || program.latest_pdf.is_outdated);

  return (
    <>
      <Link
        href={`/students/${program.student.id}?tab=programs`}
        className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:underline"
      >
        <ArrowRight className="size-4" aria-hidden />
        پرونده {program.student.full_name}
      </Link>

      <Card className="mb-6">
        <CardContent className="flex flex-col gap-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h1 className="text-2xl font-bold">{program.title}</h1>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                <ProgramStatusBadge status={program.status} />
                <span>برنامه {programTypeLabel[program.program_type]}</span>
                {program.source_voice_record_id && (
                  <Badge variant="outline">
                    <Mic aria-hidden />
                    از ویس تلگرام
                  </Badge>
                )}
                <span aria-hidden>·</span>
                <Link href={`/students/${program.student.id}`} className="hover:underline">
                  {program.student.full_name}
                </Link>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              {program.status === "draft" && (
                <Button onClick={approve} disabled={!!busy}>
                  {spinner("approve") || <CircleCheck aria-hidden />}
                  تأیید و ساخت PDF
                </Button>
              )}
              {program.status !== "draft" && (
                <Button onClick={generate} disabled={!!busy} variant={pdfOutdated ? "default" : "outline"}>
                  {spinner("pdf") || <FilePlus2 aria-hidden />}
                  {program.latest_pdf ? "ساخت PDF جدید" : "ساخت PDF"}
                </Button>
              )}
              {program.status !== "archived" && (
                <Button asChild variant="outline">
                  <Link href={`/programs/${program.id}/edit`}>
                    <Pencil aria-hidden />
                    ویرایش
                  </Link>
                </Button>
              )}
              <Button variant="outline" onClick={duplicate} disabled={!!busy}>
                {spinner("copy") || <Copy aria-hidden />}
                کپی برای دوره بعد
              </Button>
              {program.status === "approved" && (
                <ConfirmButton
                  trigger={
                    <Button variant="ghost" disabled={!!busy}>
                      <Archive aria-hidden />
                      بایگانی
                    </Button>
                  }
                  title="بایگانی برنامه؟"
                  description="برنامه و همه PDFهای آن حفظ می‌شوند اما دیگر قابل ویرایش نیست. برای تغییر، از آن کپی بگیرید."
                  confirmLabel="بایگانی شود"
                  onConfirm={archive}
                />
              )}
              {program.status === "draft" && (
                <ConfirmButton
                  trigger={
                    <Button variant="ghost" disabled={!!busy}>
                      <Trash2 aria-hidden />
                      حذف پیش‌نویس
                    </Button>
                  }
                  title="حذف پیش‌نویس؟"
                  description="این پیش‌نویس هنوز تأیید نشده و برای همیشه حذف می‌شود. برنامه‌های تأییدشده تحت تأثیر قرار نمی‌گیرند."
                  confirmLabel="حذف شود"
                  destructive
                  onConfirm={remove}
                />
              )}
            </div>
          </div>
          <dl className="grid grid-cols-2 gap-4 border-t pt-4 text-sm sm:grid-cols-5">
            <Fact label="دوره">{program.period_number ? toPersianDigits(program.period_number) : "—"}</Fact>
            <Fact label="شروع">{formatJalaliDate(program.start_date)}</Fact>
            <Fact label="پایان">{formatJalaliDate(program.end_date)}</Fact>
            <Fact label="ایجاد">{formatJalaliDate(program.created_at)}</Fact>
            <Fact label="تأیید">{formatJalaliDate(program.approved_at)}</Fact>
          </dl>
        </CardContent>
      </Card>

      {program.status === "draft" && (
        <Alert className="mb-6">
          <TriangleAlert aria-hidden />
          <AlertDescription>
            این برنامه پیش‌نویس است و تا تأیید شما نهایی نمی‌شود. پس از بازبینی، «تأیید و ساخت PDF» را بزنید.
          </AlertDescription>
        </Alert>
      )}
      {program.status !== "draft" && program.latest_pdf?.is_outdated && (
        <Alert className="mb-6">
          <TriangleAlert aria-hidden />
          <AlertDescription>
            برنامه بعد از ساخت آخرین PDF تغییر کرده است. برای چاپ نسخه به‌روز، «ساخت PDF جدید» را بزنید.
          </AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="flex flex-col gap-6 xl:col-span-2">
          <ProgramContentView program={program} />
          {program.notes && (
            <Card>
              <CardHeader>
                <CardTitle>توضیحات</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm leading-7 whitespace-pre-line">{program.notes}</p>
              </CardContent>
            </Card>
          )}
        </div>
        <Card className="self-start">
          <CardHeader>
            <CardTitle>فایل‌های PDF</CardTitle>
          </CardHeader>
          <CardContent>
            {program.status === "draft" ? (
              <p className="text-sm text-muted-foreground">PDF پس از تأیید برنامه ساخته می‌شود.</p>
            ) : (
              <PdfList programId={program.id} refreshKey={`${pdfKey}:${program.updated_at}`} />
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
