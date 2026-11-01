"""Workout voice text -> sessions/exercises.

Rules (spec §9): unspecified values stay None; ambiguous numbers are reported,
never assigned; unknown exercise names are kept as spoken; the original text
of each exercise is stored in raw_text.
"""
import re
from dataclasses import asdict, dataclass, field

from app.parsers.dictionary import EMPTY, ExerciseDictionary
from app.parsers.numbers import words_to_digits
from app.services.text import to_persian_digits

N = r"(\d+(?:\.\d+)?)"
END = r"(?![\w\u200c])"  # end of word (\w covers Persian letters; «،» must not count)

RE_FAILURE = re.compile(r"تا\s+(ناتوانی|خستگی|شکست|واماندگی)")
RE_PYRAMID = re.compile(r"(\d+(?:\s*[-–،,]?\s*\d+){2,})\s*(?:تایی|تکرار|تا)" + END)
RE_DASHED = re.compile(r"(\d+(?:\s*[-–]\s*\d+)+)\s*(?:تایی|تکرار|تا)?" + END)
RE_RANGE = re.compile(N + r"\s*(?:تا|الی)\s*" + N + r"\s*(?:تایی|تکرار|تا)" + END)
RE_SETS = re.compile(N + r"\s*(?:ست|ستی|ستِ)" + END)
RE_REPS = re.compile(N + r"\s*(?:تایی|تکرار|تا|تکراری)" + END)
RE_WEIGHT = re.compile(N + r"\s*(کیلوگرمی|کیلوگرم|کیلویی|کیلو|kg|پوندی|پوند|lb)" + END)
RE_WEIGHT_NOUNIT = re.compile(r"(?:وزنه|وزن)\s*" + N + r"(?!\s*(?:کیلو|پوند|kg|lb))" + END)
DUR = N + r"\s*(ثانیه‌ای|ثانیه|دقیقه‌ای|دقیقه)(\s*و\s*نیم)?" + END
RE_REST = re.compile(r"استراحت(?:\s*(?:بین|بعد)\s*(?:ست|حرکت)(?:\s*ها|‌ها)?)?\s*" + DUR + "|" + DUR + r"\s*استراحت")
RE_DURATION = re.compile(DUR)
RE_DISTANCE = re.compile(N + r"\s*(کیلومتر|متر)" + END)
RE_NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w.])")

SEPARATORS = re.compile(r"[،,.;؛\n]+|\s(?:و\s+)?(?:بعدش|بعد\s+از\s+اون|بعد|سپس|حرکت\s+بعدی|بعدی)\s")
GENERAL_REST = re.compile(r"(بین\s*ست|همه|کل|تمام|هر\s*ست)")
FILLERS = {"با", "حرکت", "بزن", "بزنه", "انجام", "بده", "بشه", "رو", "را", "هم", "اول", "دوم", "سوم", "و", "بعد"}
EQUIPMENT_AFTER_WITH = {"دمبل", "هالتر", "دستگاه", "کش", "سیم‌کش", "میله"}
NOTE_HINTS = ("سوپرست", "سوپر ست", "دراپ", "کنترل", "آهسته", "آروم", "تمپو", "مکث", "فول", "نیمه", "فشار")


@dataclass
class ParsedExercise:
    name: str
    matched: bool = False
    suggestion: str | None = None
    execution_type: str = "reps"
    sets: int | None = None
    reps: str | None = None
    weight_value: float | None = None
    weight_unit: str | None = None
    duration_seconds: int | None = None
    distance_value: float | None = None
    distance_unit: str | None = None
    rest_seconds: int | None = None
    notes: str | None = None
    raw_text: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class ParsedWorkout:
    session_title: str | None
    exercises: list[ParsedExercise]
    session_notes: str | None
    warnings: list[str]
    text: str
    program_type: str = "workout"

    def to_dict(self) -> dict:
        return asdict(self)


def _num(s: str) -> float:
    v = float(s)
    return int(v) if v == int(v) else v


def _seconds(value: str, unit: str, half: str | None) -> int:
    v = float(value) * (60 if unit.startswith("دقیقه") else 1)
    if half:
        v += 30 if unit.startswith("دقیقه") else 0.5
    return int(round(v))


def _cut(text: str, m: re.Match) -> str:
    """Blank out a match, keeping positions stable (to know what came first)."""
    return text[: m.start()] + " " * (m.end() - m.start()) + text[m.end() :]


def _fa(text: str | None) -> str | None:
    return to_persian_digits(text) if text else text


def _parse_segment(seg: str, dictionary: ExerciseDictionary) -> tuple[ParsedExercise | None, dict]:
    """Parse one exercise-sized chunk. Returns (exercise or None, extras)."""
    rest_text = seg
    found: dict = {}

    if m := RE_REST.search(rest_text):
        value, unit, half = (m.group(1), m.group(2), m.group(3)) if m.group(1) else (m.group(4), m.group(5), m.group(6))
        found["rest_seconds"] = _seconds(value, unit, half)
        found["general_rest"] = bool(GENERAL_REST.search(m.group(0)))
        rest_text = _cut(rest_text, m)
    if m := RE_FAILURE.search(rest_text):
        found["reps"] = f"تا {m.group(1)}"
        rest_text = _cut(rest_text, m)
    if "reps" not in found and (m := RE_RANGE.search(rest_text)):
        found["reps"] = f"{_num(m.group(1))}-{_num(m.group(2))}"
        rest_text = _cut(rest_text, m)
    if m := RE_SETS.search(rest_text):
        found["sets"] = int(float(m.group(1)))
        rest_text = _cut(rest_text, m)
    if "reps" not in found and (m := RE_PYRAMID.search(rest_text)):
        nums = re.findall(r"\d+", m.group(1))
        found["reps"] = "-".join(nums)
        rest_text = _cut(rest_text, m)
    if "reps" not in found and (m := RE_DASHED.search(rest_text)):
        found["reps"] = "-".join(re.findall(r"\d+", m.group(1)))
        rest_text = _cut(rest_text, m)
    if "reps" not in found and (m := RE_REPS.search(rest_text)):
        found["reps"] = str(_num(m.group(1)))
        rest_text = _cut(rest_text, m)
    if m := RE_WEIGHT.search(rest_text):
        unit = m.group(2)
        found["weight_value"] = _num(m.group(1))
        found["weight_unit"] = "lb" if unit.startswith("پوند") or unit == "lb" else "kg"
        rest_text = _cut(rest_text, m)
    elif m := RE_WEIGHT_NOUNIT.search(rest_text):
        found["weight_value"] = _num(m.group(1))
        found["weight_unit"] = None  # unit not stated: do not assume
        rest_text = _cut(rest_text, m)
    if m := RE_DISTANCE.search(rest_text):
        found["distance_value"] = _num(m.group(1))
        found["distance_unit"] = "km" if m.group(2) == "کیلومتر" else "m"
        rest_text = _cut(rest_text, m)
    if m := RE_DURATION.search(rest_text):
        found["duration_seconds"] = _seconds(m.group(1), m.group(2), m.group(3))
        rest_text = _cut(rest_text, m)

    leftover_numbers = RE_NUMBER.findall(rest_text)
    rest_text = RE_NUMBER.sub(lambda m: " " * len(m.group(0)), rest_text)
    # The exercise name is what was said before the first recognised value;
    # words after it are notes (or unrecognised text, flagged below).
    first_value = next((i for i, (a, b) in enumerate(zip(seg, rest_text)) if a != b), len(seg))
    head_words = rest_text[:first_value].split()
    tail_words = rest_text[first_value:].split()
    if not head_words:  # values were said first («4 ست اسکوات ...»)
        head_words, tail_words = tail_words, []
    words = head_words

    # Name = longest dictionary prefix, else leading words up to a note hint
    match = dictionary.match_prefix(words)
    if match:
        name, matched, tail = match.name, True, words[match.consumed_words :] + tail_words
    else:
        name_words: list[str] = []
        tail = []
        for i, w in enumerate(words):
            if any(w.startswith(h.split()[0]) for h in NOTE_HINTS):
                tail = words[i:]
                break
            name_words.append(w)
        tail = tail + tail_words
        while name_words and name_words[-1] in FILLERS:
            name_words.pop()
        while name_words and name_words[0] in FILLERS:
            name_words.pop(0)
        name, matched = " ".join(name_words), False

    # Drop restated equipment («... با دمبل 12 کیلویی») and fillers from notes
    note_words = list(tail)
    if len(note_words) >= 2 and note_words[0] == "با" and note_words[1] in EQUIPMENT_AFTER_WITH:
        note_words = note_words[2:]
    note_words = [w for w in note_words if w not in FILLERS or len(note_words) > 2]
    notes = " ".join(note_words).strip() or None
    if notes and all(w in FILLERS for w in notes.split()):
        notes = None

    if not name:
        return None, {**found, "leftover_numbers": leftover_numbers, "text": seg, "notes": notes}

    ex = ParsedExercise(name=name, matched=matched, raw_text=_fa(seg.strip()) or "")
    for k in ("sets", "reps", "weight_value", "weight_unit", "duration_seconds", "distance_value", "distance_unit"):
        if k in found:
            setattr(ex, k, found[k])
    if "rest_seconds" in found:
        ex.rest_seconds = found["rest_seconds"]
    ex.notes = _fa(notes)
    if notes and not any(h.split()[0] in notes for h in NOTE_HINTS):
        ex.warnings.append(f"بخشی از متن تشخیص داده نشد و در توضیحات آمد: «{_fa(notes)}»")
    if ex.duration_seconds is not None and ex.reps is None:
        ex.execution_type = "time"
    elif ex.distance_value is not None and ex.reps is None:
        ex.execution_type = "distance"
    elif (ex.duration_seconds is not None or ex.distance_value is not None) and ex.reps is not None:
        ex.execution_type = "combined"

    if not matched:
        ex.suggestion = dictionary.suggest(name)
        ex.warnings.append(
            f"«{name}» در فرهنگ لغت نیست" + (f"؛ شاید «{ex.suggestion}»؟" if ex.suggestion else "") + " (نام بدون تغییر حفظ شد)"
        )
    if ex.execution_type == "reps":
        if ex.sets is None:
            ex.warnings.append("تعداد ست گفته نشده")
        if ex.reps is None:
            ex.warnings.append("تعداد تکرار گفته نشده")
    if "weight_value" in found and found.get("weight_unit") is None:
        ex.warnings.append("واحد وزنه مشخص نیست")
    if leftover_numbers:
        ex.warnings.append("عدد بدون واحد (ثبت نشد): " + "، ".join(to_persian_digits(n) for n in leftover_numbers))
    return ex, found


# After a complete prescription («... 12 تایی») a new word that is not a modifier
# starts the next exercise — Whisper often omits commas between exercises.
_CONTINUATION = r"(?:ناتوانی|خستگی|شکست|واماندگی|با|استراحت|سوپر|سوپرست|دراپ|تا|و\s+\d|\d|کیلو|پوند|وزنه|ثانیه|دقیقه)"
RE_NEXT_EXERCISE = re.compile(
    r"(?:(?<=تایی)|(?<=تکرار)|(?<=\sتا))\s+(?:و\s+)?(?=(?!" + _CONTINUATION + r")[^\d\s])"
)


def _split_and(segment: str) -> list[str]:
    return [p for p in RE_NEXT_EXERCISE.split(segment) if p.strip()]


# Fixed misspellings Whisper produces for gym words (one meaning each, so this is a
# spelling fix, not a guess). The raw transcript is still kept and shown to the coach.
SPELLING = {
    "حالتر": "هالتر", "هالطر": "هالتر", "حالطر": "هالتر",
    "دنبل": "دمبل", "دامبل": "دمبل", "دمبول": "دمبل",
    "چکوشی": "چکشی", "چکشى": "چکشی", "چکوش": "چکش",
    "سیمکش": "سیم‌کش", "سیم کش": "سیم‌کش",
    "اسکات": "اسکوات",
}
_RE_SPELLING = re.compile(
    r"(?<![\w\u200c])(" + "|".join(sorted(map(re.escape, SPELLING), key=len, reverse=True)) + r")(?![\w\u200c])"
)


def fix_spelling(text: str) -> str:
    return _RE_SPELLING.sub(lambda m: SPELLING[m.group(1)], text)


SESSION_PREFIX = re.compile(r"^\s*جلسه\s+(\S+)\s*[:،]?\s*(.*)$")


def parse_workout(text: str, dictionary: ExerciseDictionary = EMPTY, session_title: str | None = None) -> ParsedWorkout:
    normalized = fix_spelling(words_to_digits(text))
    raw_segments = [s.strip() for s in SEPARATORS.split(normalized) if s and s.strip()]
    segments = [p.strip() for s in raw_segments for p in _split_and(s)]

    exercises: list[ParsedExercise] = []
    session_notes: list[str] = []
    warnings: list[str] = []

    for idx, seg in enumerate(segments):
        if idx == 0 and not session_title and (m := SESSION_PREFIX.match(seg)) and not re.search(r"\d", seg):
            session_title = f"جلسه {m.group(1)}" + (f": {m.group(2)}" if m.group(2) else "")
            continue
        ex, extra = _parse_segment(seg, dictionary)
        if ex:
            exercises.append(ex)
            continue
        # No exercise name in this chunk
        if "rest_seconds" in extra and not extra.get("general_rest") and exercises and exercises[-1].rest_seconds is None:
            exercises[-1].rest_seconds = extra["rest_seconds"]
            exercises[-1].raw_text = f"{exercises[-1].raw_text}، {_fa(seg)}"
            exercises[-1].warnings.append("استراحت گفته‌شده بعد از این حرکت به آن نسبت داده شد؛ بررسی کنید")
            continue
        value_keys = [k for k in ("sets", "reps", "weight_value", "weight_unit", "duration_seconds",
                                  "distance_value", "distance_unit", "rest_seconds") if k in extra]
        has_values = any(k in extra for k in ("sets", "reps", "weight_value", "duration_seconds", "distance_value"))
        prev = exercises[-1] if exercises else None
        if has_values and prev and not extra.get("leftover_numbers") and not extra.get("notes") and all(
            getattr(prev, k) is None for k in value_keys
        ):
            # «اسکوات، 4 ست» — punctuation split a name from its own values
            for k in value_keys:
                setattr(prev, k, extra[k])
            prev.raw_text = f"{prev.raw_text}، {_fa(seg)}"
            prev.warnings = [w for w in prev.warnings
                             if not (w == "تعداد ست گفته نشده" and prev.sets is not None)
                             and not (w == "تعداد تکرار گفته نشده" and prev.reps is not None)]
            continue
        if has_values:
            warnings.append(f"مقادیر بدون نام حرکت (ثبت نشد): «{_fa(seg)}»")
        session_notes.append(_fa(seg))

    if not exercises:
        warnings.append("هیچ حرکتی تشخیص داده نشد؛ متن را بررسی و اصلاح کنید")
    notes = "، ".join(session_notes) if session_notes else None
    if notes and not notes.endswith("."):
        notes += "."
    return ParsedWorkout(
        session_title=session_title,
        exercises=exercises,
        session_notes=notes,
        warnings=warnings,
        text=text.strip(),
    )
