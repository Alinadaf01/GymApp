import { test } from "node:test";
import assert from "node:assert/strict";
import { draftToPayload, emptyExercise, emptySession, move, toDraft, type ProgramDraft } from "../lib/program-draft.ts";

function draft(partial: Partial<ProgramDraft> = {}): ProgramDraft {
  return { title: "برنامه", period_number: "", start_date: "", end_date: "", notes: "", sessions: [], meals: [],
           supplements: [], ...partial };
}

test("unspecified exercise values stay null (no guessing)", () => {
  const s = emptySession();
  s.title = "پا";
  s.exercises[0].name = "اسکوات";
  s.exercises[0].sets = "۴";
  const { payload, errors } = draftToPayload(draft({ sessions: [s] }), "workout");
  assert.deepEqual(errors, {});
  const ex = payload!.sessions[0].exercises[0];
  assert.equal(ex.sets, 4);
  assert.equal(ex.reps, null);
  assert.equal(ex.weight_value, null);
  assert.equal(ex.weight_unit, null); // unit dropped when no weight
  assert.equal(ex.rest_seconds, null);
});

test("Persian digits and decimal separator are accepted", () => {
  const s = emptySession();
  s.title = "سینه";
  Object.assign(s.exercises[0], { name: "پرس", reps: "۱۲-۱۰-۸", weight_value: "۱۲٫۵", rest_seconds: "۹۰" });
  const { payload } = draftToPayload(draft({ sessions: [s], start_date: "۱۴۰۵/۸/۱", end_date: "1405/09/01" }), "workout");
  const ex = payload!.sessions[0].exercises[0];
  assert.equal(ex.reps, "12-10-8");
  assert.equal(ex.weight_value, 12.5);
  assert.equal(ex.weight_unit, "kg");
  assert.equal(ex.rest_seconds, 90);
  assert.equal(payload!.start_date, "2026-10-23");
});

test("errors are reported per field path", () => {
  const s = emptySession();
  s.exercises[0].sets = "0";
  s.exercises[0].weight_value = "abc";
  const { payload, errors } = draftToPayload(
    draft({ title: " ", sessions: [s], start_date: "1405/09/01", end_date: "1405/08/01" }), "workout");
  assert.equal(payload, undefined);
  assert.ok(errors.title);
  assert.ok(errors["sessions.0.title"]);
  assert.ok(errors["sessions.0.exercises.0.name"]);
  assert.ok(errors["sessions.0.exercises.0.sets"]);
  assert.ok(errors["sessions.0.exercises.0.weight_value"]);
  assert.ok(errors.end_date);
});

test("only content matching the type is sent", () => {
  const s = emptySession();
  const { payload } = draftToPayload(
    draft({ sessions: [s], meals: [{ key: "m", title: "صبحانه", time_text: "", content: "نان", notes: "" }] }),
    "nutrition");
  assert.deepEqual(payload!.sessions, []);
  assert.equal(payload!.meals[0].time_text, null);
});

test("toDraft round-trips API values", () => {
  const d = toDraft({
    id: "p", student: { id: "s", full_name: "x" }, title: "t", program_type: "workout", period_number: 2,
    start_date: "2026-10-23", end_date: null, status: "draft", notes: null, source_voice_record_id: null,
    created_at: "", updated_at: "", approved_at: null, latest_pdf: null, meals: [], supplements: [],
    sessions: [{ id: "a", title: "پا", notes: null, sort_order: 0, exercises: [{
      id: "e", name: "اسکوات", execution_type: "reps", sets: 4, reps: null, weight_value: "40.00", weight_unit: "kg",
      duration_seconds: null, distance_value: null, distance_unit: null, rest_seconds: 60, notes: null, raw_text: "خام",
      sort_order: 0 }] }],
  });
  assert.equal(d.start_date, "1405/08/01");
  assert.equal(d.sessions[0].exercises[0].weight_value, "40");
  assert.equal(d.sessions[0].exercises[0].reps, "");
  const { payload } = draftToPayload(d, "workout");
  const ex = payload!.sessions[0].exercises[0];
  assert.equal(ex.weight_value, 40);
  assert.equal(ex.reps, null);
  assert.equal(ex.raw_text, "خام"); // raw text kept for debugging
});

test("move swaps neighbours and ignores out of range", () => {
  assert.deepEqual(move([1, 2, 3], 0, 1), [2, 1, 3]);
  assert.deepEqual(move([1, 2, 3], 0, -1), [1, 2, 3]);
  void emptyExercise;
});
