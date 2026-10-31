"use client";

import { useEffect, useState } from "react";
import { AlertCircle, Check, Loader2, Pencil, Plus, Search, Trash2, X } from "lucide-react";
import { toast } from "sonner";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmButton } from "@/components/ui/confirm-button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch } from "@/lib/api";
import { toPersianDigits } from "@/lib/format";

type Entry = { id: string; canonical_name: string; aliases: string[] };

/** «لت، لت پول، زیربغل سیم‌کش» -> ["لت", "لت پول", "زیربغل سیم‌کش"] */
const splitAliases = (text: string) =>
  text.split(/[،,\n]/).map((s) => s.trim()).filter(Boolean);

function EntryForm({
  initial,
  submitLabel,
  onSubmit,
  onCancel,
}: {
  initial?: Entry;
  submitLabel: string;
  onSubmit: (name: string, aliases: string[]) => Promise<boolean>;
  onCancel?: () => void;
}) {
  const [name, setName] = useState(initial?.canonical_name ?? "");
  const [aliases, setAliases] = useState(initial?.aliases.join("، ") ?? "");
  const [pending, setPending] = useState(false);
  const idBase = initial?.id ?? "new";

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setPending(true);
    const ok = await onSubmit(name.trim(), splitAliases(aliases));
    setPending(false);
    if (ok && !initial) {
      setName("");
      setAliases("");
    }
  }

  return (
    <form onSubmit={submit} className="grid gap-3 sm:grid-cols-[1fr_1.5fr_auto] sm:items-end">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={`${idBase}-name`} className="text-xs text-muted-foreground">نام استاندارد حرکت</Label>
        <Input id={`${idBase}-name`} value={name} onChange={(e) => setName(e.target.value)} maxLength={200} required />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={`${idBase}-aliases`} className="text-xs text-muted-foreground">
          مترادف‌ها و شکل‌های گفتاری (با «،» جدا کنید)
        </Label>
        <Input id={`${idBase}-aliases`} value={aliases} onChange={(e) => setAliases(e.target.value)} />
      </div>
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={pending || !name.trim()}>
          {pending ? <Loader2 className="animate-spin" aria-hidden /> : initial ? <Check aria-hidden /> : <Plus aria-hidden />}
          {submitLabel}
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

export function DictionaryManager() {
  const [entries, setEntries] = useState<Entry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [editing, setEditing] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiFetch<Entry[]>("/api/exercises/dictionary")
      .then((d) => !cancelled && setEntries(d))
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, []);

  async function create(name: string, aliases: string[]) {
    try {
      const e = await apiFetch<Entry>("/api/exercises/dictionary", {
        method: "POST", body: JSON.stringify({ canonical_name: name, aliases }),
      });
      setEntries((list) => [...(list ?? []), e].sort((a, b) => a.canonical_name.localeCompare(b.canonical_name, "fa")));
      toast.success("حرکت به فرهنگ لغت اضافه شد.");
      return true;
    } catch (err) {
      toast.error((err as Error).message);
      return false;
    }
  }

  async function update(id: string, name: string, aliases: string[]) {
    try {
      const e = await apiFetch<Entry>(`/api/exercises/dictionary/${id}`, {
        method: "PUT", body: JSON.stringify({ canonical_name: name, aliases }),
      });
      setEntries((list) => list!.map((x) => (x.id === id ? e : x)));
      setEditing(null);
      toast.success("ذخیره شد.");
      return true;
    } catch (err) {
      toast.error((err as Error).message);
      return false;
    }
  }

  async function remove(id: string) {
    try {
      await apiFetch(`/api/exercises/dictionary/${id}`, { method: "DELETE" });
      setEntries((list) => list!.filter((x) => x.id !== id));
    } catch (err) {
      toast.error((err as Error).message);
    }
  }

  const needle = q.trim().replace(/[\s‌]/g, "");
  const shown = (entries ?? []).filter(
    (e) =>
      !needle ||
      [e.canonical_name, ...e.aliases].some((t) => t.replace(/[\s‌]/g, "").includes(needle)),
  );

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>افزودن حرکت</CardTitle>
          <CardDescription>
            Parser ویس، نام‌ها و مترادف‌های این فهرست را به «نام استاندارد» تبدیل می‌کند. نامی که در فهرست نباشد بدون
            تغییر حفظ و برای تأیید شما علامت‌گذاری می‌شود.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <EntryForm submitLabel="افزودن" onSubmit={create} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="gap-3">
          <CardTitle>
            فرهنگ لغت حرکات {entries && <span className="text-sm font-normal text-muted-foreground">({toPersianDigits(entries.length)})</span>}
          </CardTitle>
          <div className="relative max-w-sm">
            <Search className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
            <Input value={q} onChange={(e) => setQ(e.target.value)} className="pr-9" placeholder="جستجو در نام‌ها و مترادف‌ها"
              aria-label="جستجو در فرهنگ لغت" />
          </div>
        </CardHeader>
        <CardContent>
          {error && (
            <Alert variant="destructive">
              <AlertCircle aria-hidden />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          {!entries && !error && <Skeleton className="h-32 w-full" />}
          {entries && shown.length === 0 && <p className="py-6 text-center text-sm text-muted-foreground">موردی نیست.</p>}
          <ul className="divide-y">
            {shown.map((e) => (
              <li key={e.id} className="py-3" data-testid="dictionary-entry">
                {editing === e.id ? (
                  <EntryForm initial={e} submitLabel="ذخیره" onSubmit={(n, a) => update(e.id, n, a)}
                    onCancel={() => setEditing(null)} />
                ) : (
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-medium">{e.canonical_name}</p>
                      {e.aliases.length > 0 && (
                        <div className="mt-1 flex flex-wrap gap-1">
                          {e.aliases.map((a) => <Badge key={a} variant="outline">{a}</Badge>)}
                        </div>
                      )}
                    </div>
                    <div className="flex">
                      <Button variant="ghost" size="icon" aria-label={`ویرایش ${e.canonical_name}`} onClick={() => setEditing(e.id)}>
                        <Pencil />
                      </Button>
                      <ConfirmButton
                        trigger={<Button variant="ghost" size="icon" aria-label={`حذف ${e.canonical_name}`}><Trash2 /></Button>}
                        title={`حذف «${e.canonical_name}»؟`}
                        description="فقط از فرهنگ لغت حذف می‌شود؛ برنامه‌های ثبت‌شده تغییری نمی‌کنند."
                        confirmLabel="حذف شود"
                        destructive
                        onConfirm={() => remove(e.id)}
                      />
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
