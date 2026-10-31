"use client";

import { useEffect, useId, useState } from "react";
import { AlertCircle, Loader2, Pencil, Plus, Trash2, X } from "lucide-react";
import { toast } from "sonner";

import { TimeLineChart } from "@/components/charts/time-line-chart";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmButton } from "@/components/ui/confirm-button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch } from "@/lib/api";
import { formatJalaliDate, formatNumber } from "@/lib/format";
import { isoToJalaliInput, parseDecimalInput, parseJalaliInput } from "@/lib/jalali";
import { MEASUREMENT_FIELDS, type MeasurementKey } from "@/lib/labels";
import type { Measurement } from "@/lib/types";

type FormValues = { date: string; notes: string } & Record<MeasurementKey, string>;

const today = () => isoToJalaliInput(new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Tehran" }).format(new Date()));

function emptyForm(): FormValues {
  return { date: today(), notes: "", ...Object.fromEntries(MEASUREMENT_FIELDS.map((f) => [f.key, ""])) } as FormValues;
}

function fromMeasurement(m: Measurement): FormValues {
  return {
    date: isoToJalaliInput(m.measured_at),
    notes: m.notes ?? "",
    ...Object.fromEntries(MEASUREMENT_FIELDS.map((f) => [f.key, m[f.key] ? String(Number(m[f.key])) : ""])),
  } as FormValues;
}

function MeasurementForm({ initial, onSubmit, onCancel }: {
  initial?: Measurement;
  onSubmit: (payload: Record<string, unknown>) => Promise<boolean>;
  onCancel?: () => void;
}) {
  const uid = useId();
  const [v, setV] = useState<FormValues>(() => (initial ? fromMeasurement(initial) : emptyForm()));
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const date = parseJalaliInput(v.date);
    if (!date.ok || !date.iso) return setError("تاریخ را به شکل ۱۴۰۵/۰۸/۰۹ وارد کنید.");
    const payload: Record<string, unknown> = { measured_at: date.iso, notes: v.notes.trim() || null };
    for (const f of MEASUREMENT_FIELDS) {
      const p = parseDecimalInput(v[f.key]);
      if (!p.ok) return setError(`${f.label} باید عدد باشد.`);
      payload[f.key] = p.value === null ? null : Math.round(p.value * 10) / 10;
    }
    if (MEASUREMENT_FIELDS.every((f) => payload[f.key] === null)) return setError("حداقل یک اندازه را وارد کنید.");
    setPending(true);
    const ok = await onSubmit(payload);
    setPending(false);
    if (ok && !initial) setV(emptyForm());
  }

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-4">
      {error && (
        <Alert variant="destructive">
          <AlertCircle aria-hidden />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="col-span-2 flex flex-col gap-1.5 sm:col-span-1">
          <Label htmlFor={`${uid}-date`} className="text-xs text-muted-foreground">تاریخ اندازه‌گیری</Label>
          <Input id={`${uid}-date`} value={v.date} onChange={(e) => setV({ ...v, date: e.target.value })} dir="ltr" inputMode="numeric" />
        </div>
        {MEASUREMENT_FIELDS.map((f) => (
          <div key={f.key} className="flex flex-col gap-1.5">
            <Label htmlFor={`${uid}-${f.key}`} className="text-xs text-muted-foreground">
              {f.label} ({f.unit === "کیلوگرم" ? "kg" : "cm"})
            </Label>
            <Input id={`${uid}-${f.key}`} value={v[f.key]} inputMode="decimal" dir="ltr"
              onChange={(e) => setV({ ...v, [f.key]: e.target.value })} />
          </div>
        ))}
        <div className="col-span-2 flex flex-col gap-1.5 sm:col-span-4">
          <Label htmlFor={`${uid}-notes`} className="text-xs text-muted-foreground">توضیحات</Label>
          <Input id={`${uid}-notes`} value={v.notes} onChange={(e) => setV({ ...v, notes: e.target.value })} maxLength={2000} />
        </div>
      </div>
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={pending}>
          {pending ? <Loader2 className="animate-spin" aria-hidden /> : !initial && <Plus aria-hidden />}
          {initial ? "ذخیره" : "ثبت اندازه‌ها"}
        </Button>
        {onCancel && (
          <Button type="button" size="sm" variant="ghost" onClick={onCancel}>
            <X aria-hidden />
            انصراف
          </Button>
        )}
      </div>
    </form>
  );
}

const CHARTS: { key: MeasurementKey; title: string; unit: string }[] = [
  { key: "weight_kg", title: "وزن", unit: "کیلوگرم" },
  { key: "waist_cm", title: "دور کمر", unit: "سانتی‌متر" },
  { key: "arm_cm", title: "دور بازو", unit: "سانتی‌متر" },
];

export function Measurements({ studentId, onChanged }: { studentId: string; onChanged: () => void }) {
  const [rows, setRows] = useState<Measurement[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const [editing, setEditing] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiFetch<Measurement[]>(`/api/students/${studentId}/measurements`)
      .then((r) => !cancelled && setRows(r))
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [studentId, version]);

  const refresh = () => {
    setVersion((x) => x + 1);
    onChanged(); // current weight in the profile header may have changed
  };

  async function save(payload: Record<string, unknown>, id?: string) {
    try {
      await apiFetch(id ? `/api/measurements/${id}` : `/api/students/${studentId}/measurements`, {
        method: id ? "PUT" : "POST", body: JSON.stringify(payload),
      });
      toast.success(id ? "ذخیره شد." : "اندازه‌ها ثبت شدند.");
      setEditing(null);
      refresh();
      return true;
    } catch (e) {
      toast.error((e as Error).message);
      return false;
    }
  }

  async function remove(id: string) {
    try {
      await apiFetch(`/api/measurements/${id}`, { method: "DELETE" });
      refresh();
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>ثبت اندازه‌های بدن</CardTitle>
          <CardDescription>همه فیلدها اختیاری‌اند؛ فقط اندازه‌هایی را که گرفته‌اید وارد کنید. وزن فعلی پرونده از آخرین وزن ثبت‌شده به‌روز می‌شود.</CardDescription>
        </CardHeader>
        <CardContent>
          <MeasurementForm onSubmit={(p) => save(p)} />
        </CardContent>
      </Card>

      {error && <p className="text-sm text-destructive">{error}</p>}
      {!rows && !error && <Skeleton className="h-48 w-full" />}

      {rows && (
        <Card>
          <CardHeader>
            <CardTitle>نمودارها</CardTitle>
            <CardDescription>فقط داده‌های ثبت‌شده نمایش داده می‌شوند؛ هیچ مقداری برآورد یا پیش‌بینی نمی‌شود.</CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-8 lg:grid-cols-2">
            {CHARTS.map((c) => (
              <TimeLineChart key={c.key} title={c.title} unit={c.unit}
                points={rows.filter((r) => r[c.key] !== null).map((r) => ({ date: r.measured_at, value: Number(r[c.key]) }))} />
            ))}
          </CardContent>
        </Card>
      )}

      {rows && rows.length > 0 && (
        <Card>
          <CardHeader><CardTitle>سوابق اندازه‌گیری</CardTitle></CardHeader>
          <CardContent>
            {/* relative: keeps sr-only (absolute) labels inside the scroll box; otherwise they widen the RTL page */}
            <div className="relative overflow-x-auto">
              <table className="w-full min-w-[720px] text-sm" data-testid="measurements-table">
                <thead className="bg-muted/50 text-right text-xs text-muted-foreground">
                  <tr>
                    <th scope="col" className="px-3 py-2 font-medium">تاریخ</th>
                    {MEASUREMENT_FIELDS.map((f) => <th key={f.key} scope="col" className="px-3 py-2 font-medium">{f.label}</th>)}
                    <th scope="col" className="px-3 py-2 font-medium">توضیحات</th>
                    <th scope="col"><span className="sr-only">عملیات</span></th>
                  </tr>
                </thead>
                <tbody>
                  {[...rows].reverse().map((m) =>
                    editing === m.id ? (
                      <tr key={m.id}>
                        <td colSpan={MEASUREMENT_FIELDS.length + 3} className="border-t p-3">
                          <MeasurementForm initial={m} onSubmit={(p) => save(p, m.id)} onCancel={() => setEditing(null)} />
                        </td>
                      </tr>
                    ) : (
                      <tr key={m.id}>
                        <td className="border-t px-3 py-2 whitespace-nowrap">{formatJalaliDate(m.measured_at)}</td>
                        {MEASUREMENT_FIELDS.map((f) => (
                          <td key={f.key} className="border-t px-3 py-2">{m[f.key] ? formatNumber(m[f.key]) : "—"}</td>
                        ))}
                        <td className="border-t px-3 py-2">{m.notes}</td>
                        <td className="border-t px-1 py-1">
                          <div className="flex justify-end">
                            <Button variant="ghost" size="icon" aria-label={`ویرایش اندازه‌گیری ${formatJalaliDate(m.measured_at)}`}
                              onClick={() => setEditing(m.id)}>
                              <Pencil />
                            </Button>
                            <ConfirmButton
                              trigger={<Button variant="ghost" size="icon" aria-label={`حذف اندازه‌گیری ${formatJalaliDate(m.measured_at)}`}><Trash2 /></Button>}
                              title="حذف این اندازه‌گیری؟" description="این ردیف برای همیشه حذف می‌شود." confirmLabel="حذف شود"
                              destructive onConfirm={() => remove(m.id)} />
                          </div>
                        </td>
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
