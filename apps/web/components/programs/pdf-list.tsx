"use client";

import { useEffect, useState } from "react";
import { Download, FileText, Printer, TriangleAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch, apiUrl } from "@/lib/api";
import { formatJalaliDate, toPersianDigits } from "@/lib/format";
import type { PdfInfo } from "@/lib/types";

function formatTime(iso: string) {
  return new Intl.DateTimeFormat("fa-IR", { timeZone: "Asia/Tehran", hour: "2-digit", minute: "2-digit" }).format(
    new Date(iso),
  );
}

/** All PDF versions of a program. Files are served only through the authenticated API. */
export function PdfList({ programId, refreshKey }: { programId: string; refreshKey: string }) {
  const [pdfs, setPdfs] = useState<PdfInfo[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiFetch<PdfInfo[]>(`/api/programs/${programId}/pdfs`)
      .then((d) => !cancelled && setPdfs(d))
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [programId, refreshKey]);

  if (error) return <p className="text-sm text-destructive">{error}</p>;
  if (!pdfs) return <Skeleton className="h-12 w-full" />;
  if (pdfs.length === 0) return <p className="text-sm text-muted-foreground">هنوز PDFی ساخته نشده است.</p>;

  return (
    <ul className="divide-y">
      {pdfs.map((p) => (
        <li key={p.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
          <div className="flex items-center gap-3">
            <FileText className="size-5 text-muted-foreground" aria-hidden />
            <div>
              <p className="text-sm font-medium">نسخه {toPersianDigits(p.version)}</p>
              <p className="text-xs text-muted-foreground">
                {formatJalaliDate(p.created_at)} · ساعت {formatTime(p.created_at)}
              </p>
            </div>
            {p.is_outdated && (
              <Badge variant="outline" title="برنامه بعد از ساخت این PDF تغییر کرده است">
                <TriangleAlert aria-hidden />
                قدیمی‌تر از برنامه
              </Badge>
            )}
          </div>
          <div className="flex gap-2">
            <Button asChild variant="outline" size="sm">
              <a href={apiUrl(`/api/pdfs/${p.id}/download?inline=1`)} target="_blank" rel="noopener">
                <Printer aria-hidden />
                مشاهده و چاپ
              </a>
            </Button>
            <Button asChild variant="ghost" size="sm">
              <a href={apiUrl(`/api/pdfs/${p.id}/download`)}>
                <Download aria-hidden />
                دانلود
              </a>
            </Button>
          </div>
        </li>
      ))}
    </ul>
  );
}
