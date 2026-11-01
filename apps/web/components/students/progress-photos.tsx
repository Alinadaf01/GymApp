"use client";

import { useEffect, useId, useMemo, useState } from "react";
import { AlertCircle, Columns2, ImagePlus, Loader2, Trash2, X } from "lucide-react";
import { toast } from "sonner";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmButton } from "@/components/ui/confirm-button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch, apiUrl } from "@/lib/api";
import { formatJalaliDate } from "@/lib/format";
import { isoToJalaliInput, parseJalaliInput } from "@/lib/jalali";
import { PHOTO_VIEWS, photoViewLabel } from "@/lib/labels";
import type { PhotoView, ProgressPhoto } from "@/lib/types";

const ACCEPT = ["image/jpeg", "image/png", "image/webp"];

function todayIso() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Tehran" }).format(new Date());
}

/* eslint-disable @next/next/no-img-element -- private images come from the authenticated API (cookie);
   next/image would fetch them server-side without the coach's session. */

function Thumb({ photo, onOpen }: { photo: ProgressPhoto; onOpen: (p: ProgressPhoto) => void }) {
  return (
    <button type="button" onClick={() => onOpen(photo)}
      className="group relative aspect-[3/4] w-full cursor-zoom-in overflow-hidden rounded-lg border bg-muted"
      aria-label={`نمایش عکس ${photoViewLabel[photo.view_type]} ${formatJalaliDate(photo.capture_date)}`}>
      <img src={apiUrl(photo.thumb_url)} alt="" loading="lazy" className="size-full object-cover transition group-hover:scale-[1.02]" />
    </button>
  );
}

function Missing() {
  return (
    <div className="flex aspect-[3/4] w-full items-center justify-center rounded-lg border border-dashed text-xs text-muted-foreground">
      ثبت نشده
    </div>
  );
}

function UploadForm({ studentId, consentRecorded, onUploaded }: {
  studentId: string; consentRecorded: boolean; onUploaded: () => void;
}) {
  const uid = useId();
  const [date, setDate] = useState(() => isoToJalaliInput(todayIso()));
  const [picked, setPicked] = useState<Partial<Record<PhotoView, File>>>({});
  const [notes, setNotes] = useState("");
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const previews = useMemo(
    () => Object.fromEntries(Object.entries(picked).map(([k, f]) => [k, URL.createObjectURL(f!)])) as Partial<Record<PhotoView, string>>,
    [picked],
  );
  useEffect(() => () => Object.values(previews).forEach((u) => u && URL.revokeObjectURL(u)), [previews]);

  function pick(view: PhotoView, e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (!ACCEPT.includes(file.type)) return setError("فقط تصویر JPG، PNG یا WEBP.");
    setError(null);
    setPicked((p) => ({ ...p, [view]: file }));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const parsed = parseJalaliInput(date);
    if (!parsed.ok || !parsed.iso) return setError("تاریخ را به شکل ۱۴۰۵/۰۸/۰۹ وارد کنید.");
    const views = PHOTO_VIEWS.filter((v) => picked[v]);
    if (views.length === 0) return setError("حداقل یک عکس انتخاب کنید.");
    if (!consentRecorded && !consent) return setError("رضایت شاگرد برای ثبت تصاویر را تأیید کنید.");
    setPending(true);
    const failed: string[] = [];
    for (const view of views) {
      const fd = new FormData();
      fd.append("file", picked[view]!);
      fd.append("view_type", view);
      fd.append("capture_date", parsed.iso);
      fd.append("consent", String(consent || consentRecorded));
      if (notes.trim()) fd.append("notes", notes.trim());
      try {
        await apiFetch(`/api/students/${studentId}/photos`, { method: "POST", body: fd });
        setPicked((p) => {
          const next = { ...p };
          delete next[view];
          return next;
        });
      } catch (err) {
        failed.push(`${photoViewLabel[view]}: ${(err as Error).message}`);
      }
    }
    setPending(false);
    if (failed.length) setError(failed.join("\n"));
    else {
      toast.success("عکس‌ها ثبت شدند.");
      setNotes("");
    }
    onUploaded();
  }

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-4">
      {error && (
        <Alert variant="destructive">
          <AlertCircle aria-hidden />
          <AlertDescription className="whitespace-pre-line">{error}</AlertDescription>
        </Alert>
      )}
      <div className="grid gap-4 sm:grid-cols-[12rem_1fr]">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={`${uid}-date`}>تاریخ عکس (شمسی)</Label>
          <Input id={`${uid}-date`} value={date} onChange={(e) => setDate(e.target.value)} dir="ltr" inputMode="numeric" />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={`${uid}-notes`}>توضیحات (اختیاری)</Label>
          <Input id={`${uid}-notes`} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={2000} />
        </div>
      </div>
      <div className="grid max-w-lg grid-cols-3 gap-3">
        {PHOTO_VIEWS.map((view) => (
          <div key={view} className="flex flex-col gap-1.5">
            <span className="text-xs text-muted-foreground">{photoViewLabel[view]} (اختیاری)</span>
            <label className="relative flex aspect-[3/4] cursor-pointer items-center justify-center overflow-hidden rounded-lg border border-dashed bg-muted/40 text-muted-foreground hover:bg-muted">
              {previews[view] ? (
                <img src={previews[view]} alt={`پیش‌نمایش ${photoViewLabel[view]}`} className="size-full object-cover" />
              ) : (
                <ImagePlus className="size-6" aria-hidden />
              )}
              <input type="file" accept={ACCEPT.join(",")} className="sr-only" aria-label={`عکس ${photoViewLabel[view]}`}
                onChange={(e) => pick(view, e)} />
            </label>
            {picked[view] && (
              <Button type="button" variant="ghost" size="sm" onClick={() => setPicked((p) => {
                const next = { ...p };
                delete next[view];
                return next;
              })}>
                <X aria-hidden />
                برداشتن
              </Button>
            )}
          </div>
        ))}
      </div>
      {!consentRecorded && (
        <label className="flex items-start gap-2 text-sm leading-6">
          <input type="checkbox" className="mt-1 size-4 accent-primary" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
          رضایت شاگرد برای ثبت و نگهداری تصاویر پیشرفت گرفته شده است.
        </label>
      )}
      <Button type="submit" disabled={pending} className="self-start">
        {pending && <Loader2 className="animate-spin" aria-hidden />}
        ثبت عکس‌ها
      </Button>
    </form>
  );
}

export function ProgressPhotos({ studentId, consentRecorded, archived, onChanged }: {
  studentId: string; consentRecorded: boolean; archived: boolean; onChanged: () => void;
}) {
  const [photos, setPhotos] = useState<ProgressPhoto[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const [open, setOpen] = useState<ProgressPhoto | null>(null);
  const [cmpA, setCmpA] = useState<string>("");
  const [cmpB, setCmpB] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    apiFetch<ProgressPhoto[]>(`/api/students/${studentId}/photos`)
      .then((p) => !cancelled && setPhotos(p))
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [studentId, version]);

  const byDate = useMemo(() => {
    const map = new Map<string, Partial<Record<PhotoView, ProgressPhoto>>>();
    for (const p of photos ?? []) {
      const row = map.get(p.capture_date) ?? {};
      row[p.view_type] = p;
      map.set(p.capture_date, row);
    }
    return map; // newest first (API order)
  }, [photos]);
  const dates = [...byDate.keys()];
  // Default comparison: oldest vs newest
  const a = cmpA && byDate.has(cmpA) ? cmpA : dates[dates.length - 1];
  const b = cmpB && byDate.has(cmpB) ? cmpB : dates[0];

  async function remove(p: ProgressPhoto) {
    try {
      await apiFetch(`/api/photos/${p.id}`, { method: "DELETE" });
      setOpen(null);
      setVersion((v) => v + 1);
      onChanged();
      toast.success("عکس حذف شد.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      {!archived && (
        <Card>
          <CardHeader>
            <CardTitle>ثبت عکس پیشرفت</CardTitle>
            <CardDescription>
              هر سه نما اختیاری‌اند. تصاویر خصوصی‌اند، اطلاعات مکان (EXIF) حذف می‌شود و فقط پس از ورود مربی دیده می‌شوند.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <UploadForm studentId={studentId} consentRecorded={consentRecorded}
              onUploaded={() => { setVersion((v) => v + 1); onChanged(); }} />
          </CardContent>
        </Card>
      )}

      {error && <p className="text-sm text-destructive">{error}</p>}
      {!photos && !error && <Skeleton className="h-48 w-full" />}
      {photos && photos.length === 0 && (
        <p className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">هنوز عکسی ثبت نشده است.</p>
      )}

      {dates.length >= 2 && (
        <Card data-testid="photo-compare" className="max-w-2xl">
          <CardHeader className="gap-3">
            <CardTitle className="flex items-center gap-2">
              <Columns2 className="size-4" aria-hidden />
              مقایسه دو تاریخ
            </CardTitle>
            <div className="grid grid-cols-2 gap-3">
              {[["تاریخ اول", a, setCmpA], ["تاریخ دوم", b, setCmpB]].map(([label, value, set]) => (
                <NativeSelect key={label as string} aria-label={label as string} value={value as string}
                  onChange={(e) => (set as (v: string) => void)(e.target.value)}>
                  {dates.map((d) => <option key={d} value={d}>{formatJalaliDate(d)}</option>)}
                </NativeSelect>
              ))}
            </div>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {PHOTO_VIEWS.map((view) => (
              <div key={view}>
                <p className="mb-1.5 text-xs font-medium text-muted-foreground">{photoViewLabel[view]}</p>
                <div className="grid max-w-md grid-cols-2 gap-3">
                  {[a, b].map((d, i) => {
                    const p = byDate.get(d)?.[view];
                    return p ? <Thumb key={i} photo={p} onOpen={setOpen} /> : <Missing key={i} />;
                  })}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {dates.length > 0 && (
        <Card>
          <CardHeader><CardTitle>آلبوم</CardTitle></CardHeader>
          <CardContent className="flex flex-col gap-5">
            {dates.map((d) => (
              <section key={d} aria-label={`عکس‌های ${formatJalaliDate(d)}`} data-testid="album-date">
                <h3 className="mb-2 text-sm font-semibold">{formatJalaliDate(d)}</h3>
                <div className="grid max-w-lg grid-cols-3 gap-3">
                  {PHOTO_VIEWS.map((view) => {
                    const p = byDate.get(d)?.[view];
                    return (
                      <div key={view} className="flex flex-col gap-1">
                        {p ? <Thumb photo={p} onOpen={setOpen} /> : <Missing />}
                        <span className="text-center text-xs text-muted-foreground">{photoViewLabel[view]}</span>
                      </div>
                    );
                  })}
                </div>
              </section>
            ))}
          </CardContent>
        </Card>
      )}

      <Dialog open={!!open} onOpenChange={(o) => !o && setOpen(null)}>
        {open && (
          <DialogContent>
            <DialogTitle>
              {photoViewLabel[open.view_type]} — {formatJalaliDate(open.capture_date)}
            </DialogTitle>
            <DialogDescription>{open.notes || "بدون توضیحات"}</DialogDescription>
            <img src={apiUrl(open.url)} alt={`عکس ${photoViewLabel[open.view_type]} ${formatJalaliDate(open.capture_date)}`}
              className="mx-auto max-h-[70svh] w-auto rounded-lg object-contain" />
            <ConfirmButton
              trigger={<Button variant="outline" size="sm" className="self-start"><Trash2 aria-hidden />حذف این عکس</Button>}
              title="حذف عکس؟"
              description="عکس و فایل آن برای همیشه حذف می‌شوند."
              confirmLabel="حذف شود"
              destructive
              onConfirm={() => remove(open)}
            />
          </DialogContent>
        )}
      </Dialog>
    </div>
  );
}
