/**
 * Editable (string-based) model of a program for the editor, plus conversion to
 * the API payload. Pure functions — unit tested in tests/program-draft.test.mts.
 *
 * Rule from the spec: a value the coach did not enter stays null. Nothing here
 * fills in defaults for sets/reps/weight/rest.
 */
import { isoToJalaliInput, parseDecimalInput, parseJalaliInput, toAsciiDigits } from "./jalali.ts";
import type { ExecutionType, Program, ProgramType } from "./types.ts";

let keySeq = 0;
export const newKey = () => `k${++keySeq}`;

export type ExerciseDraft = {
  key: string;
  name: string;
  execution_type: ExecutionType;
  sets: string;
  reps: string;
  weight_value: string;
  weight_unit: string;
  duration_seconds: string;
  distance_value: string;
  distance_unit: string;
  rest_seconds: string;
  notes: string;
  raw_text: string | null;
};

export type SessionDraft = { key: string; title: string; notes: string; exercises: ExerciseDraft[] };
export type MealDraft = { key: string; title: string; time_text: string; content: string; notes: string };
export type SupplementDraft = { key: string; name: string; amount_text: string; timing_text: string; notes: string };

export type ProgramDraft = {
  title: string;
  period_number: string;
  start_date: string; // Jalali text
  end_date: string; // Jalali text
  notes: string;
  sessions: SessionDraft[];
  meals: MealDraft[];
  supplements: SupplementDraft[];
};

const s = (v: string | number | null | undefined) => (v === null || v === undefined ? "" : String(v));

export function emptyExercise(): ExerciseDraft {
  return {
    key: newKey(), name: "", execution_type: "reps", sets: "", reps: "", weight_value: "", weight_unit: "kg",
    duration_seconds: "", distance_value: "", distance_unit: "m", rest_seconds: "", notes: "", raw_text: null,
  };
}

export const SESSION_ORDINALS = ["اول", "دوم", "سوم", "چهارم", "پنجم", "ششم", "هفتم", "هشتم", "نهم", "دهم"];

export function emptySession(): SessionDraft {
  return { key: newKey(), title: "", notes: "", exercises: [emptyExercise()] };
}
export const emptyMeal = (): MealDraft => ({ key: newKey(), title: "", time_text: "", content: "", notes: "" });
export const emptySupplement = (): SupplementDraft => ({
  key: newKey(), name: "", amount_text: "", timing_text: "", notes: "",
});

export function toDraft(p: Program): ProgramDraft {
  return {
    title: p.title,
    period_number: s(p.period_number),
    start_date: isoToJalaliInput(p.start_date),
    end_date: isoToJalaliInput(p.end_date),
    notes: s(p.notes),
    sessions: p.sessions.map((x) => ({
      key: newKey(),
      title: x.title,
      notes: s(x.notes),
      exercises: x.exercises.map((e) => ({
        key: newKey(),
        name: e.name,
        execution_type: e.execution_type,
        sets: s(e.sets),
        reps: s(e.reps),
        weight_value: s(e.weight_value).replace(/\.0+$|(\.\d*?)0+$/, "$1"),
        weight_unit: e.weight_unit ?? (e.weight_value ? "" : "kg"),
        duration_seconds: s(e.duration_seconds),
        distance_value: s(e.distance_value).replace(/\.0+$|(\.\d*?)0+$/, "$1"),
        distance_unit: e.distance_unit ?? (e.distance_value ? "" : "m"),
        rest_seconds: s(e.rest_seconds),
        notes: s(e.notes),
        raw_text: e.raw_text,
      })),
    })),
    meals: p.meals.map((m) => ({
      key: newKey(), title: m.title, time_text: s(m.time_text), content: m.content, notes: s(m.notes),
    })),
    supplements: p.supplements.map((x) => ({
      key: newKey(), name: x.name, amount_text: s(x.amount_text), timing_text: s(x.timing_text), notes: s(x.notes),
    })),
  };
}

export type DraftErrors = Record<string, string>;

export type ExercisePayload = {
  name: string;
  execution_type: ExecutionType;
  sets: number | null;
  reps: string | null;
  weight_value: number | null;
  weight_unit: string | null;
  duration_seconds: number | null;
  distance_value: number | null;
  distance_unit: string | null;
  rest_seconds: number | null;
  notes: string | null;
  raw_text: string | null;
};

export type ProgramPayload = {
  title: string;
  period_number: number | null;
  start_date: string | null;
  end_date: string | null;
  notes: string | null;
  sessions: { title: string; notes: string | null; exercises: ExercisePayload[] }[];
  meals: { title: string; time_text: string | null; content: string; notes: string | null }[];
  supplements: { name: string; amount_text: string | null; timing_text: string | null; notes: string | null }[];
};

const text = (v: string) => v.trim() || null;

function int(v: string, min: number, max: number, label: string, path: string, errors: DraftErrors) {
  const t = toAsciiDigits(v).trim();
  if (!t) return null;
  if (!/^\d+$/.test(t) || Number(t) < min || Number(t) > max) {
    errors[path] = `${label} باید عدد صحیح بین ${min.toLocaleString("fa-IR")} و ${max.toLocaleString("fa-IR")} باشد.`;
    return null;
  }
  return Number(t);
}

function dec(v: string, max: number, label: string, path: string, errors: DraftErrors) {
  const p = parseDecimalInput(v);
  if (!p.ok || (p.value !== null && p.value > max)) {
    errors[path] = `${label} باید عدد معتبر باشد.`;
    return null;
  }
  return p.value;
}

/** Validate and convert to the API payload (ProgramUpdate). */
export function draftToPayload(d: ProgramDraft, type: ProgramType): { payload?: ProgramPayload; errors: DraftErrors } {
  const errors: DraftErrors = {};
  if (!d.title.trim()) errors.title = "عنوان برنامه الزامی است.";
  const period_number = int(d.period_number, 1, 999, "شماره دوره", "period_number", errors);
  const start = parseJalaliInput(d.start_date);
  const end = parseJalaliInput(d.end_date);
  if (!start.ok) errors.start_date = "تاریخ را به شکل ۱۴۰۵/۰۸/۰۹ وارد کنید.";
  if (!end.ok) errors.end_date = "تاریخ را به شکل ۱۴۰۵/۰۸/۰۹ وارد کنید.";
  if (start.ok && end.ok && start.iso && end.iso && end.iso < start.iso)
    errors.end_date = "تاریخ پایان نمی‌تواند قبل از تاریخ شروع باشد.";

  const sessions: ProgramPayload["sessions"] =
    type === "workout"
      ? d.sessions.map((x, si) => {
          if (!x.title.trim()) errors[`sessions.${si}.title`] = "عنوان جلسه الزامی است.";
          return {
            title: x.title.trim(),
            notes: text(x.notes),
            exercises: x.exercises.map((e, ei) => {
              const p = `sessions.${si}.exercises.${ei}`;
              if (!e.name.trim()) errors[`${p}.name`] = "نام حرکت الزامی است.";
              const weight_value = dec(e.weight_value, 1000, "وزنه", `${p}.weight_value`, errors);
              const distance_value = dec(e.distance_value, 100000, "مسافت", `${p}.distance_value`, errors);
              return {
                name: e.name.trim(),
                execution_type: e.execution_type,
                sets: int(e.sets, 1, 100, "ست", `${p}.sets`, errors),
                reps: text(toAsciiDigits(e.reps)),
                weight_value,
                weight_unit: weight_value === null ? null : text(e.weight_unit),
                duration_seconds: int(e.duration_seconds, 1, 86400, "مدت", `${p}.duration_seconds`, errors),
                distance_value,
                distance_unit: distance_value === null ? null : text(e.distance_unit),
                rest_seconds: int(e.rest_seconds, 0, 3600, "استراحت", `${p}.rest_seconds`, errors),
                notes: text(e.notes),
                raw_text: e.raw_text,
              };
            }),
          };
        })
      : [];

  const meals: ProgramPayload["meals"] =
    type === "nutrition"
      ? d.meals.map((m, i) => {
          if (!m.title.trim()) errors[`meals.${i}.title`] = "عنوان وعده الزامی است.";
          if (!m.content.trim()) errors[`meals.${i}.content`] = "محتوای وعده الزامی است.";
          return { title: m.title.trim(), time_text: text(m.time_text), content: m.content.trim(), notes: text(m.notes) };
        })
      : [];

  const supplements: ProgramPayload["supplements"] =
    type === "supplement" || type === "vitamin"
      ? d.supplements.map((x, i) => {
          if (!x.name.trim()) errors[`supplements.${i}.name`] = "نام الزامی است.";
          return {
            name: x.name.trim(), amount_text: text(x.amount_text), timing_text: text(x.timing_text), notes: text(x.notes),
          };
        })
      : [];

  if (Object.keys(errors).length) return { errors };
  return {
    errors,
    payload: {
      title: d.title.trim(),
      period_number,
      start_date: start.ok ? start.iso : null,
      end_date: end.ok ? end.iso : null,
      notes: text(d.notes),
      sessions,
      meals,
      supplements,
    },
  };
}

/** Move an item up/down in a list (returns a new array). */
export function move<T>(list: T[], index: number, delta: -1 | 1): T[] {
  const to = index + delta;
  if (to < 0 || to >= list.length) return list;
  const next = list.slice();
  [next[index], next[to]] = [next[to], next[index]];
  return next;
}
