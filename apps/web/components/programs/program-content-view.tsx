import { formatNumber, formatSeconds, toPersianDigits } from "@/lib/format";
import { unitLabel } from "@/lib/labels";
import { SESSION_ORDINALS } from "@/lib/program-draft";
import type { Exercise, Program } from "@/lib/types";

const Dash = () => <span className="text-muted-foreground">—</span>;

function withUnit(value: string | null, unit: string | null) {
  return value ? `${formatNumber(value, 2)} ${unitLabel(unit)}`.trim() : null;
}

function Cell({ children }: { children: React.ReactNode }) {
  return <td className="border-t px-3 py-2 align-top">{children ?? <Dash />}</td>;
}

function ExerciseTable({ exercises }: { exercises: Exercise[] }) {
  const timed = exercises.some((e) => e.duration_seconds !== null);
  const distanced = exercises.some((e) => e.distance_value !== null);
  return (
    <div className="relative overflow-x-auto">
      <table className="w-full min-w-[640px] text-sm">
        <thead className="bg-muted/50 text-right text-xs text-muted-foreground">
          <tr>
            <th className="w-10 px-3 py-2 font-medium">ردیف</th>
            <th className="px-3 py-2 font-medium">حرکت</th>
            <th className="px-3 py-2 font-medium">ست</th>
            <th className="px-3 py-2 font-medium">تکرار</th>
            <th className="px-3 py-2 font-medium">وزنه</th>
            {timed && <th className="px-3 py-2 font-medium">زمان</th>}
            {distanced && <th className="px-3 py-2 font-medium">مسافت</th>}
            <th className="px-3 py-2 font-medium">استراحت</th>
            <th className="px-3 py-2 font-medium">توضیحات</th>
          </tr>
        </thead>
        <tbody>
          {exercises.map((e, i) => (
            <tr key={e.id}>
              <Cell>{toPersianDigits(i + 1)}</Cell>
              <Cell>
                <span className="font-medium">{e.name}</span>
              </Cell>
              <Cell>{e.sets !== null ? toPersianDigits(e.sets) : null}</Cell>
              <Cell>{e.reps ? toPersianDigits(e.reps) : null}</Cell>
              <Cell>{withUnit(e.weight_value, e.weight_unit)}</Cell>
              {timed && <Cell>{e.duration_seconds !== null ? formatSeconds(e.duration_seconds) : null}</Cell>}
              {distanced && <Cell>{withUnit(e.distance_value, e.distance_unit)}</Cell>}
              <Cell>{e.rest_seconds !== null ? formatSeconds(e.rest_seconds) : null}</Cell>
              <Cell>{e.notes ? <span className="whitespace-pre-line">{e.notes}</span> : <span />}</Cell>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SimpleTable({ head, rows }: { head: string[]; rows: (React.ReactNode | null)[][] }) {
  return (
    <div className="relative overflow-x-auto">
      <table className="w-full min-w-[560px] text-sm">
        <thead className="bg-muted/50 text-right text-xs text-muted-foreground">
          <tr>
            {head.map((h) => (
              <th key={h} className="px-3 py-2 font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {r.map((c, j) => (
                <Cell key={j}>{c}</Cell>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Read-only rendering of a program's content, mirroring the printed PDF. */
export function ProgramContentView({ program }: { program: Program }) {
  if (program.program_type === "workout") {
    if (program.sessions.length === 0) return <p className="text-sm text-muted-foreground">جلسه‌ای ثبت نشده است.</p>;
    return (
      <div className="flex flex-col gap-6">
        {program.sessions.map((s, i) => (
          <section key={s.id} className="overflow-hidden rounded-lg border">
            <h3 className="border-b bg-card px-4 py-2.5 font-semibold">
              {/* A title like «جلسه اول» (chosen in the bot) is shown as is, not «جلسه اول: جلسه اول» */}
              {s.title.startsWith("جلسه") ? s.title : `جلسه ${SESSION_ORDINALS[i] ?? toPersianDigits(i + 1)}: ${s.title}`}
            </h3>
            {s.exercises.length ? (
              <ExerciseTable exercises={s.exercises} />
            ) : (
              <p className="px-4 py-3 text-sm text-muted-foreground">حرکتی ثبت نشده است.</p>
            )}
            {s.notes && <p className="border-t px-4 py-2 text-sm whitespace-pre-line text-muted-foreground">{s.notes}</p>}
          </section>
        ))}
      </div>
    );
  }
  if (program.program_type === "nutrition") {
    if (program.meals.length === 0) return <p className="text-sm text-muted-foreground">وعده‌ای ثبت نشده است.</p>;
    return (
      <div className="overflow-hidden rounded-lg border">
        <SimpleTable
          head={["ردیف", "وعده", "ساعت", "مواد غذایی و مقدار", "توضیحات"]}
          rows={program.meals.map((m, i) => [
            toPersianDigits(i + 1),
            <span key="t" className="font-medium">{m.title}</span>,
            m.time_text ? toPersianDigits(m.time_text) : null,
            <span key="c" className="whitespace-pre-line">{m.content}</span>,
            m.notes ? <span className="whitespace-pre-line">{m.notes}</span> : <span />,
          ])}
        />
      </div>
    );
  }
  if (program.supplements.length === 0) return <p className="text-sm text-muted-foreground">قلمی ثبت نشده است.</p>;
  return (
    <div className="overflow-hidden rounded-lg border">
      <SimpleTable
        head={["ردیف", "نام", "مقدار", "زمان مصرف", "توضیحات"]}
        rows={program.supplements.map((x, i) => [
          toPersianDigits(i + 1),
          <span key="n" className="font-medium">{x.name}</span>,
          x.amount_text ? toPersianDigits(x.amount_text) : null,
          x.timing_text,
          x.notes ? <span className="whitespace-pre-line">{x.notes}</span> : <span />,
        ])}
      />
    </div>
  );
}
