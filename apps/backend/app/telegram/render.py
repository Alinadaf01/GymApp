"""Telegram message texts (HTML parse mode — everything user-provided is escaped)."""
from html import escape

from app.pdf.formatting import number, seconds
from app.services.text import to_persian_digits

TYPE_LABELS = {"workout": "تمرینی", "nutrition": "غذایی", "supplement": "مکمل", "vitamin": "ویتامین"}
UNIT = {"kg": "کیلوگرم", "lb": "پوند", "m": "متر", "km": "کیلومتر"}
MAX_TEXT = 3500  # Telegram limit is 4096 characters per message


def e(text) -> str:
    return escape(str(text)) if text is not None else ""


def fa(value) -> str:
    return to_persian_digits(str(value))


def _exercise_line(i: int, ex: dict) -> str:
    parts = []
    if ex.get("sets") is not None:
        parts.append(f"{fa(ex['sets'])} ست")
    if ex.get("reps"):
        parts.append(f"{fa(ex['reps'])} تکرار" if any(c.isdigit() for c in ex["reps"]) else e(ex["reps"]))
    if ex.get("weight_value") is not None:
        unit = UNIT.get(ex.get("weight_unit") or "", "(واحد نامشخص)")
        parts.append(f"وزنه {number(ex['weight_value'])} {unit}")
    if ex.get("duration_seconds") is not None:
        parts.append(f"زمان {seconds(ex['duration_seconds'])}")
    if ex.get("distance_value") is not None:
        parts.append(f"مسافت {number(ex['distance_value'])} {UNIT.get(ex.get('distance_unit') or '', '')}")
    if ex.get("rest_seconds") is not None:
        parts.append(f"استراحت {seconds(ex['rest_seconds'])}")
    mark = "" if ex.get("matched") else "❓ "
    line = f"{fa(i)}. {mark}<b>{e(ex['name'])}</b>"
    line += " — " + " · ".join(parts) if parts else " — <i>مقداری گفته نشده</i>"
    if ex.get("notes"):
        line += f"\n    📝 {e(ex['notes'])}"
    for w in ex.get("warnings", []):
        line += f"\n    ⚠️ {e(w)}"
    return line


def structure_text(payload: dict | None, program_type: str, session_title: str | None) -> str:
    if payload is None:
        return "⚠️ ساختار برنامه از متن تشخیص داده نشد. متن اصلاح‌شده را بفرستید یا در پنل بازبینی کنید."
    lines: list[str] = []
    if program_type == "workout":
        title = payload.get("session_title") or session_title or "جلسه"
        lines.append(f"🏋️ <b>{e(title)}</b>")
        lines += [_exercise_line(i, ex) for i, ex in enumerate(payload.get("exercises", []), 1)]
        if payload.get("session_notes"):
            lines.append(f"🗒 توضیحات جلسه: {e(payload['session_notes'])}")
    elif program_type == "nutrition":
        lines.append("🥗 <b>وعده‌ها</b>")
        for i, m in enumerate(payload.get("meals", []), 1):
            time = f" ({e(m['time_text'])})" if m.get("time_text") else ""
            lines.append(f"{fa(i)}. <b>{e(m['title'])}</b>{time}: {e(m.get('content') or '—')}")
            lines += [f"    ⚠️ {e(w)}" for w in m.get("warnings", [])]
    else:
        lines.append(f"💊 <b>اقلام {TYPE_LABELS.get(program_type, '')}</b>")
        for i, x in enumerate(payload.get("supplements", []), 1):
            details = " · ".join(e(v) for v in (x.get("amount_text"), x.get("timing_text")) if v)
            lines.append(f"{fa(i)}. <b>{e(x['name'])}</b>" + (f" — {details}" if details else ""))
            lines += [f"    ⚠️ {e(w)}" for w in x.get("warnings", [])]
    lines += [f"⚠️ {e(w)}" for w in payload.get("warnings", [])]
    return "\n".join(lines)


def review_text(student_name: str, program_type: str, session_title: str | None, transcript: str | None,
                corrected: str | None, payload: dict | None) -> str:
    source = corrected or transcript or ""
    if len(source) > 1200:
        source = source[:1200] + "…"
    label = "متن اصلاح‌شده" if corrected else "متن ویس"
    body = (
        f"👤 {e(student_name)} · برنامه {TYPE_LABELS.get(program_type, '')}\n\n"
        f"🎙 <b>{label}:</b>\n<blockquote>{e(source)}</blockquote>\n\n"
        f"{structure_text(payload, program_type, session_title)}\n\n"
        "تا تأیید شما چیزی ثبت نهایی نمی‌شود. ❓ یعنی نام حرکت در فرهنگ لغت نیست."
    )
    return body[:MAX_TEXT]
