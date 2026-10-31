"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useState } from "react";
import {
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Loader2,
  Plus,
  Settings2,
  Trash2,
  TriangleAlert,
} from "lucide-react";
import { toast } from "sonner";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import { apiFetch } from "@/lib/api";
import { toPersianDigits } from "@/lib/format";
import { DISTANCE_UNITS, executionTypeLabel, programTypeLabel, WEIGHT_UNITS } from "@/lib/labels";
import {
  draftToPayload,
  emptyExercise,
  emptyMeal,
  emptySession,
  emptySupplement,
  move,
  SESSION_ORDINALS,
  toDraft,
  type DraftErrors,
  type ExerciseDraft,
  type MealDraft,
  type ProgramDraft,
  type SessionDraft,
  type SupplementDraft,
} from "@/lib/program-draft";
import type { ExecutionType, Program } from "@/lib/types";

// ---- small building blocks ---------------------------------------------------------

function Field({
  label,
  error,
  className,
  children,
  htmlFor,
}: {
  label: string;
  error?: string;
  className?: string;
  children: React.ReactNode;
  htmlFor: string;
}) {
  return (
    <div className={`flex min-w-0 flex-col gap-1.5 ${className ?? ""}`}>
      <Label htmlFor={htmlFor} className="text-xs text-muted-foreground">
        {label}
      </Label>
      {children}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}

function IconButton({ label, onClick, disabled, children }: {
  label: string; onClick: () => void; disabled?: boolean; children: React.ReactNode;
}) {
  return (
    <Button type="button" variant="ghost" size="icon" className="size-8" aria-label={label} title={label}
      onClick={onClick} disabled={disabled}>
      {children}
    </Button>
  );
}

function MoveButtons({ index, count, onMove, what }: {
  index: number; count: number; onMove: (d: -1 | 1) => void; what: string;
}) {
  return (
    <>
      <IconButton label={`انتقال ${what} به بالا`} onClick={() => onMove(-1)} disabled={index === 0}>
        <ChevronUp />
      </IconButton>
      <IconButton label={`انتقال ${what} به پایین`} onClick={() => onMove(1)} disabled={index === count - 1}>
        <ChevronDown />
      </IconButton>
    </>
  );
}

// ---- workout -------------------------------------------------------------------------

function ExerciseRow({
  ex, index, count, path, errors, onChange, onMove, onRemove,
}: {
  ex: ExerciseDraft; index: number; count: number; path: string; errors: DraftErrors;
  onChange: (patch: Partial<ExerciseDraft>) => void; onMove: (d: -1 | 1) => void; onRemove: () => void;
}) {
  const uid = useId();
  const id = (f: string) => `${uid}-${f}`;
  const err = (f: string) => errors[`${path}.${f}`];
  const hasAdvanced = !!(ex.duration_seconds || ex.distance_value || ex.execution_type !== "reps");
  const [more, setMore] = useState(hasAdvanced);
  const bind = (f: keyof ExerciseDraft) => ({
    id: id(f),
    value: ex[f] as string,
    "aria-invalid": !!err(f),
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
      onChange({ [f]: e.target.value } as Partial<ExerciseDraft>),
  });

  return (
    <li className="rounded-lg border bg-background/60 p-3" data-testid="exercise-row">
      {/* Mobile: number + actions on their own row so the name gets the full width */}
      <div className="mb-3 flex flex-wrap items-start gap-2 sm:flex-nowrap">
        <span className="order-1 flex size-7 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-semibold text-accent-foreground sm:mt-6">
          {toPersianDigits(index + 1)}
        </span>
        <Field label="نام حرکت" htmlFor={id("name")} error={err("name")} className="order-3 basis-full sm:order-2 sm:basis-auto sm:flex-1">
          <Input {...bind("name")} maxLength={200} />
        </Field>
        <div className="order-2 ms-auto flex shrink-0 sm:order-3 sm:mt-5">
          <MoveButtons index={index} count={count} onMove={onMove} what="حرکت" />
          <IconButton label={more ? "بستن جزئیات بیشتر" : "جزئیات بیشتر"} onClick={() => setMore((m) => !m)}>
            <Settings2 />
          </IconButton>
          <IconButton label="حذف حرکت" onClick={onRemove}>
            <Trash2 />
          </IconButton>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-12">
        <Field label="ست" htmlFor={id("sets")} error={err("sets")} className="lg:col-span-1">
          <Input {...bind("sets")} inputMode="numeric" dir="ltr" />
        </Field>
        <Field label="تکرار" htmlFor={id("reps")} error={err("reps")} className="lg:col-span-2">
          <Input {...bind("reps")} dir="ltr" maxLength={64} />
        </Field>
        <Field label="وزنه" htmlFor={id("weight_value")} error={err("weight_value")} className="col-span-2 sm:col-span-2 lg:col-span-3">
          <div className="flex gap-1.5">
            <Input {...bind("weight_value")} inputMode="decimal" dir="ltr" className="min-w-0" />
            <NativeSelect aria-label="واحد وزنه" className="w-28 shrink-0" value={ex.weight_unit}
              onChange={(e) => onChange({ weight_unit: e.target.value })}>
              {WEIGHT_UNITS.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
              {ex.weight_unit && !WEIGHT_UNITS.some((u) => u.value === ex.weight_unit) && (
                <option value={ex.weight_unit}>{ex.weight_unit}</option>
              )}
            </NativeSelect>
          </div>
        </Field>
        <Field label="استراحت (ثانیه)" htmlFor={id("rest_seconds")} error={err("rest_seconds")} className="lg:col-span-2">
          <Input {...bind("rest_seconds")} inputMode="numeric" dir="ltr" />
        </Field>
        <Field label="توضیحات" htmlFor={id("notes")} className="col-span-2 sm:col-span-4 lg:col-span-4">
          <Input {...bind("notes")} maxLength={2000} />
        </Field>
      </div>
      {more && (
        <div className="mt-3 grid grid-cols-2 gap-3 border-t pt-3 sm:grid-cols-4">
          <Field label="نوع اجرا" htmlFor={id("execution_type")}>
            <NativeSelect id={id("execution_type")} value={ex.execution_type}
              onChange={(e) => onChange({ execution_type: e.target.value as ExecutionType })}>
              {(Object.keys(executionTypeLabel) as ExecutionType[]).map((t) => (
                <option key={t} value={t}>{executionTypeLabel[t]}</option>
              ))}
            </NativeSelect>
          </Field>
          <Field label="مدت (ثانیه)" htmlFor={id("duration_seconds")} error={err("duration_seconds")}>
            <Input {...bind("duration_seconds")} inputMode="numeric" dir="ltr" />
          </Field>
          <Field label="مسافت" htmlFor={id("distance_value")} error={err("distance_value")} className="col-span-2">
            <div className="flex gap-1.5">
              <Input {...bind("distance_value")} inputMode="decimal" dir="ltr" className="min-w-0" />
              <NativeSelect aria-label="واحد مسافت" className="w-28 shrink-0" value={ex.distance_unit}
                onChange={(e) => onChange({ distance_unit: e.target.value })}>
                {DISTANCE_UNITS.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
              </NativeSelect>
            </div>
          </Field>
          {ex.raw_text && (
            <p className="col-span-2 text-xs text-muted-foreground sm:col-span-4">متن خام: {ex.raw_text}</p>
          )}
        </div>
      )}
    </li>
  );
}

function SessionCard({
  session, index, count, errors, onChange, onMove, onRemove,
}: {
  session: SessionDraft; index: number; count: number; errors: DraftErrors;
  onChange: (s: SessionDraft) => void; onMove: (d: -1 | 1) => void; onRemove: () => void;
}) {
  const uid = useId();
  const path = `sessions.${index}`;
  const setExercises = (exercises: ExerciseDraft[]) => onChange({ ...session, exercises });
  const label = `جلسه ${SESSION_ORDINALS[index] ?? toPersianDigits(index + 1)}`;

  return (
    <Card className="gap-3" data-testid="session-card">
      <CardHeader className="flex-row items-end gap-2">
        <Field label={label} htmlFor={`${uid}-title`} error={errors[`${path}.title`]} className="flex-1">
          <Input id={`${uid}-title`} value={session.title} maxLength={200}
            aria-invalid={!!errors[`${path}.title`]}
            onChange={(e) => onChange({ ...session, title: e.target.value })} />
        </Field>
        <div className="flex shrink-0">
          <MoveButtons index={index} count={count} onMove={onMove} what="جلسه" />
          <IconButton label={`حذف ${label}`} onClick={() => {
            if (session.exercises.some((e) => e.name.trim()) && !window.confirm(`${label} با همه حرکاتش حذف شود؟`)) return;
            onRemove();
          }}>
            <Trash2 />
          </IconButton>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <ol className="flex flex-col gap-3">
          {session.exercises.map((ex, i) => (
            <ExerciseRow key={ex.key} ex={ex} index={i} count={session.exercises.length}
              path={`${path}.exercises.${i}`} errors={errors}
              onChange={(patch) => setExercises(session.exercises.map((x) => (x.key === ex.key ? { ...x, ...patch } : x)))}
              onMove={(d) => setExercises(move(session.exercises, i, d))}
              onRemove={() => setExercises(session.exercises.filter((x) => x.key !== ex.key))} />
          ))}
        </ol>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <Button type="button" variant="outline" size="sm" className="self-start"
            onClick={() => setExercises([...session.exercises, emptyExercise()])}>
            <Plus aria-hidden />
            افزودن حرکت
          </Button>
          <Field label="توضیحات جلسه" htmlFor={`${uid}-notes`} className="flex-1">
            <Input id={`${uid}-notes`} value={session.notes} maxLength={5000}
              onChange={(e) => onChange({ ...session, notes: e.target.value })} />
          </Field>
        </div>
      </CardContent>
    </Card>
  );
}

// ---- nutrition / supplements ---------------------------------------------------------

function MealCard({ meal, index, count, errors, onChange, onMove, onRemove }: {
  meal: MealDraft; index: number; count: number; errors: DraftErrors;
  onChange: (m: MealDraft) => void; onMove: (d: -1 | 1) => void; onRemove: () => void;
}) {
  const uid = useId();
  const p = `meals.${index}`;
  return (
    <li className="rounded-lg border bg-card p-3" data-testid="meal-row">
      <div className="flex items-end gap-2">
        <Field label="وعده" htmlFor={`${uid}-t`} error={errors[`${p}.title`]} className="flex-1">
          <Input id={`${uid}-t`} value={meal.title} maxLength={200}
            onChange={(e) => onChange({ ...meal, title: e.target.value })} />
        </Field>
        <Field label="ساعت" htmlFor={`${uid}-h`} className="w-28">
          <Input id={`${uid}-h`} value={meal.time_text} dir="ltr" maxLength={32}
            onChange={(e) => onChange({ ...meal, time_text: e.target.value })} />
        </Field>
        <div className="flex shrink-0">
          <MoveButtons index={index} count={count} onMove={onMove} what="وعده" />
          <IconButton label="حذف وعده" onClick={onRemove}><Trash2 /></IconButton>
        </div>
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <Field label="مواد غذایی و مقدار" htmlFor={`${uid}-c`} error={errors[`${p}.content`]}>
          <Textarea id={`${uid}-c`} rows={3} value={meal.content} maxLength={5000}
            onChange={(e) => onChange({ ...meal, content: e.target.value })} />
        </Field>
        <Field label="توضیحات" htmlFor={`${uid}-n`}>
          <Textarea id={`${uid}-n`} rows={3} value={meal.notes} maxLength={5000}
            onChange={(e) => onChange({ ...meal, notes: e.target.value })} />
        </Field>
      </div>
    </li>
  );
}

function SupplementRow({ item, index, count, errors, onChange, onMove, onRemove }: {
  item: SupplementDraft; index: number; count: number; errors: DraftErrors;
  onChange: (m: SupplementDraft) => void; onMove: (d: -1 | 1) => void; onRemove: () => void;
}) {
  const uid = useId();
  const p = `supplements.${index}`;
  const bind = (f: keyof SupplementDraft) => ({
    id: `${uid}-${f}`, value: item[f], onChange: (e: React.ChangeEvent<HTMLInputElement>) =>
      onChange({ ...item, [f]: e.target.value }),
  });
  return (
    <li className="rounded-lg border bg-card p-3" data-testid="supplement-row">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-12 lg:items-end">
        <Field label="نام" htmlFor={`${uid}-name`} error={errors[`${p}.name`]} className="col-span-2 lg:col-span-3">
          <Input {...bind("name")} maxLength={200} />
        </Field>
        <Field label="مقدار اعلام‌شده" htmlFor={`${uid}-amount_text`} className="lg:col-span-2">
          <Input {...bind("amount_text")} maxLength={100} />
        </Field>
        <Field label="زمان مصرف" htmlFor={`${uid}-timing_text`} className="lg:col-span-2">
          <Input {...bind("timing_text")} maxLength={100} />
        </Field>
        <Field label="توضیحات" htmlFor={`${uid}-notes`} className="col-span-2 lg:col-span-3">
          <Input {...bind("notes")} maxLength={5000} />
        </Field>
        <div className="col-span-2 flex justify-end lg:col-span-2">
          <MoveButtons index={index} count={count} onMove={onMove} what="قلم" />
          <IconButton label="حذف قلم" onClick={onRemove}><Trash2 /></IconButton>
        </div>
      </div>
    </li>
  );
}

// ---- editor --------------------------------------------------------------------------

/** A new program opens with one empty block to fill in (not saved until «ذخیره»). */
function initialDraft(program: Program): ProgramDraft {
  const d = toDraft(program);
  if (program.program_type === "workout" && d.sessions.length === 0) d.sessions = [emptySession()];
  if (program.program_type === "nutrition" && d.meals.length === 0) d.meals = [emptyMeal()];
  if ((program.program_type === "supplement" || program.program_type === "vitamin") && d.supplements.length === 0)
    d.supplements = [emptySupplement()];
  return d;
}

export function ProgramEditor({ program }: { program: Program }) {
  const router = useRouter();
  const [draft, setDraft] = useState<ProgramDraft>(() => initialDraft(program));
  const [errors, setErrors] = useState<DraftErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [pending, setPending] = useState(false);
  const uid = useId();

  // Warn before leaving the browser tab with unsaved changes
  useEffect(() => {
    if (!dirty) return;
    const handler = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);

  function update(patch: Partial<ProgramDraft>) {
    setDraft((d) => ({ ...d, ...patch }));
    setDirty(true);
  }

  async function save() {
    setFormError(null);
    const { payload, errors: errs } = draftToPayload(draft, program.program_type);
    setErrors(errs);
    if (!payload) {
      setFormError("لطفاً خطاهای مشخص‌شده را برطرف کنید.");
      return;
    }
    setPending(true);
    try {
      await apiFetch<Program>(`/api/programs/${program.id}`, { method: "PUT", body: JSON.stringify(payload) });
    } catch (e) {
      setFormError((e as Error).message);
      setPending(false);
      return;
    }
    // Page stays mounted (hidden) after navigation: leave it in a clean state
    setPending(false);
    setDirty(false);
    toast.success("برنامه ذخیره شد.");
    router.push(`/programs/${program.id}`);
  }

  const type = program.program_type;
  const f = (k: keyof ProgramDraft) => ({
    id: `${uid}-${k}`,
    value: draft[k] as string,
    "aria-invalid": !!errors[k],
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => update({ [k]: e.target.value }),
  });

  return (
    <form onSubmit={(e) => { e.preventDefault(); save(); }} noValidate className="flex flex-col gap-6 pb-24">
      {program.status === "approved" && (
        <Alert>
          <TriangleAlert aria-hidden />
          <AlertDescription>
            این برنامه تأیید شده است. تغییرات ذخیره می‌شوند و PDFهای قبلی حفظ می‌شوند؛ برای چاپ نسخه جدید، بعد از ذخیره
            «ساخت PDF جدید» را بزنید.
          </AlertDescription>
        </Alert>
      )}
      {formError && (
        <Alert variant="destructive">
          <AlertCircle aria-hidden />
          <AlertDescription>{formError}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle>
            مشخصات برنامه {programTypeLabel[type]} — {program.student.full_name}
          </CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="عنوان" htmlFor={`${uid}-title`} error={errors.title} className="sm:col-span-2">
            <Input {...f("title")} maxLength={200} />
          </Field>
          <Field label="شماره دوره" htmlFor={`${uid}-period_number`} error={errors.period_number}>
            <Input {...f("period_number")} inputMode="numeric" dir="ltr" />
          </Field>
          <div className="hidden lg:block" />
          <Field label="تاریخ شروع (شمسی، مثل ۱۴۰۵/۰۸/۰۱)" htmlFor={`${uid}-start_date`} error={errors.start_date}>
            <Input {...f("start_date")} inputMode="numeric" dir="ltr" />
          </Field>
          <Field label="تاریخ پایان (اختیاری)" htmlFor={`${uid}-end_date`} error={errors.end_date}>
            <Input {...f("end_date")} inputMode="numeric" dir="ltr" />
          </Field>
          <Field label="توضیحات کلی" htmlFor={`${uid}-notes`} className="sm:col-span-2 lg:col-span-4">
            <Textarea {...f("notes")} rows={2} maxLength={5000} />
          </Field>
        </CardContent>
      </Card>

      {type === "workout" && (
        <section aria-label="جلسات" className="flex flex-col gap-4">
          {draft.sessions.map((s, i) => (
            <SessionCard key={s.key} session={s} index={i} count={draft.sessions.length} errors={errors}
              onChange={(next) => update({ sessions: draft.sessions.map((x) => (x.key === s.key ? next : x)) })}
              onMove={(d) => update({ sessions: move(draft.sessions, i, d) })}
              onRemove={() => update({ sessions: draft.sessions.filter((x) => x.key !== s.key) })} />
          ))}
          <Button type="button" variant="outline" className="self-start"
            onClick={() => update({ sessions: [...draft.sessions, emptySession()] })}>
            <Plus aria-hidden />
            افزودن جلسه
          </Button>
        </section>
      )}

      {type === "nutrition" && (
        <Card>
          <CardHeader><CardTitle>وعده‌ها</CardTitle></CardHeader>
          <CardContent className="flex flex-col gap-3">
            <ol className="flex flex-col gap-3">
              {draft.meals.map((m, i) => (
                <MealCard key={m.key} meal={m} index={i} count={draft.meals.length} errors={errors}
                  onChange={(next) => update({ meals: draft.meals.map((x) => (x.key === m.key ? next : x)) })}
                  onMove={(d) => update({ meals: move(draft.meals, i, d) })}
                  onRemove={() => update({ meals: draft.meals.filter((x) => x.key !== m.key) })} />
              ))}
            </ol>
            <Button type="button" variant="outline" size="sm" className="self-start"
              onClick={() => update({ meals: [...draft.meals, emptyMeal()] })}>
              <Plus aria-hidden />
              افزودن وعده
            </Button>
          </CardContent>
        </Card>
      )}

      {(type === "supplement" || type === "vitamin") && (
        <Card>
          <CardHeader>
            <CardTitle>اقلام {programTypeLabel[type]}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <p className="text-xs text-muted-foreground">
              فقط مقدار و زمانی که خودتان اعلام می‌کنید ثبت و چاپ می‌شود؛ سامانه دوز یا توصیه‌ای اضافه نمی‌کند.
            </p>
            <ol className="flex flex-col gap-3">
              {draft.supplements.map((x, i) => (
                <SupplementRow key={x.key} item={x} index={i} count={draft.supplements.length} errors={errors}
                  onChange={(next) => update({ supplements: draft.supplements.map((y) => (y.key === x.key ? next : y)) })}
                  onMove={(d) => update({ supplements: move(draft.supplements, i, d) })}
                  onRemove={() => update({ supplements: draft.supplements.filter((y) => y.key !== x.key) })} />
              ))}
            </ol>
            <Button type="button" variant="outline" size="sm" className="self-start"
              onClick={() => update({ supplements: [...draft.supplements, emptySupplement()] })}>
              <Plus aria-hidden />
              افزودن قلم
            </Button>
          </CardContent>
        </Card>
      )}

      <div className="fixed inset-x-0 bottom-0 z-30 border-t bg-card/95 px-4 py-3 backdrop-blur lg:right-64">
        <div className="flex items-center gap-2">
          <Button type="submit" size="lg" disabled={pending}>
            {pending && <Loader2 className="animate-spin" aria-hidden />}
            ذخیره
          </Button>
          <Button asChild variant="outline" size="lg">
            <Link
              href={`/programs/${program.id}`}
              onClick={() => {
                // Discard edits so the hidden (Activity-preserved) editor does not resurface them
                setDraft(initialDraft(program));
                setErrors({});
                setDirty(false);
              }}
            >
              انصراف
            </Link>
          </Button>
          {dirty && <span className="text-xs text-muted-foreground">تغییرات ذخیره نشده</span>}
        </div>
      </div>
    </form>
  );
}
