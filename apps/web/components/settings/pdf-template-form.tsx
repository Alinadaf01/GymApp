"use client";

import { useEffect, useRef, useState } from "react";
import { AlertCircle, ImagePlus, Loader2, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch, apiUrl } from "@/lib/api";
import type { PdfTemplate } from "@/lib/types";

const ACCEPT = ["image/jpeg", "image/png", "image/webp"];

export function PdfTemplateForm() {
  const [tpl, setTpl] = useState<PdfTemplate | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [logoBust, setLogoBust] = useState(0);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let cancelled = false;
    apiFetch<PdfTemplate>("/api/settings/pdf-template")
      .then((t) => !cancelled && setTpl(t))
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, []);

  if (!tpl) return error ? <p className="text-sm text-destructive">{error}</p> : <Skeleton className="h-64 w-full" />;

  const set = (k: keyof PdfTemplate) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setTpl({ ...tpl, [k]: e.target.value });

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    try {
      const { has_logo: _ignored, ...body } = tpl!;
      void _ignored;
      setTpl(await apiFetch<PdfTemplate>("/api/settings/pdf-template", { method: "PUT", body: JSON.stringify(body) }));
      toast.success("تنظیمات سربرگ ذخیره شد. PDFهای جدید با این تنظیمات ساخته می‌شوند.");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setPending(false);
    }
  }

  async function uploadLogo(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (!ACCEPT.includes(file.type)) return setError("لوگو باید JPG، PNG یا WEBP باشد.");
    const fd = new FormData();
    fd.append("file", file);
    try {
      setTpl(await apiFetch<PdfTemplate>("/api/settings/logo", { method: "PUT", body: fd }));
      setLogoBust(Date.now());
      toast.success("لوگو ذخیره شد.");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function removeLogo() {
    try {
      await apiFetch("/api/settings/logo", { method: "DELETE" });
      setTpl({ ...tpl!, has_logo: false });
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>سربرگ PDF</CardTitle>
        <CardDescription>
          روی همه PDFهای جدید چاپ می‌شود. PDFهای قبلی تغییر نمی‌کنند. قالب برای چاپ سیاه‌وسفید طراحی شده است.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={save} className="flex flex-col gap-4" noValidate>
          {error && (
            <Alert variant="destructive">
              <AlertCircle aria-hidden />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <div className="flex flex-col gap-2">
            <span className="text-sm font-medium">لوگو</span>
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex h-16 w-40 items-center justify-center overflow-hidden rounded-md border bg-white">
                {tpl.has_logo ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={apiUrl(`/api/settings/logo?v=${logoBust}`)} alt="لوگوی فعلی" className="max-h-full max-w-full object-contain" />
                ) : (
                  <span className="text-xs text-muted-foreground">بدون لوگو</span>
                )}
              </div>
              <Button type="button" variant="outline" size="sm" onClick={() => fileRef.current?.click()}>
                <ImagePlus aria-hidden />
                {tpl.has_logo ? "تغییر لوگو" : "بارگذاری لوگو"}
              </Button>
              {tpl.has_logo && (
                <Button type="button" variant="ghost" size="sm" onClick={removeLogo}>
                  <Trash2 aria-hidden />
                  حذف
                </Button>
              )}
              <input ref={fileRef} type="file" accept={ACCEPT.join(",")} className="sr-only" tabIndex={-1}
                aria-label="فایل لوگو" onChange={uploadLogo} />
            </div>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="club_name">نام باشگاه</Label>
              <Input id="club_name" value={tpl.club_name} onChange={set("club_name")} maxLength={100} />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="coach_name">نام مربی</Label>
              <Input id="coach_name" value={tpl.coach_name} onChange={set("coach_name")} maxLength={100} />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="tpl_phone">شماره تماس</Label>
              <Input id="tpl_phone" value={tpl.phone} onChange={set("phone")} dir="ltr" maxLength={40} />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="primary_color">رنگ اصلی</Label>
              <div className="flex gap-2">
                <input type="color" aria-label="انتخاب رنگ" value={tpl.primary_color} onChange={set("primary_color")}
                  className="h-10 w-12 cursor-pointer rounded-md border bg-card p-1" />
                <Input id="primary_color" value={tpl.primary_color} onChange={set("primary_color")} dir="ltr" maxLength={7} />
              </div>
            </div>
            <div className="flex flex-col gap-2 sm:col-span-2">
              <Label htmlFor="footer_text">متن پایین صفحه</Label>
              <Input id="footer_text" value={tpl.footer_text} onChange={set("footer_text")} maxLength={300} />
            </div>
          </div>
          <Button type="submit" disabled={pending} className="self-start">
            {pending && <Loader2 className="animate-spin" aria-hidden />}
            ذخیره سربرگ
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
