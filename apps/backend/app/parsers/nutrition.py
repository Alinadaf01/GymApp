"""Nutrition voice text -> meals. Content is kept in the coach's words; no
calories or diet logic is added (spec §6.3)."""
import re
from dataclasses import asdict, dataclass, field

from app.parsers.numbers import words_to_digits
from app.services.text import to_persian_digits

MEALS = [
    ("قبل از خواب", "قبل از خواب"),
    ("قبل از تمرین", "قبل از تمرین"),
    ("بعد از تمرین", "بعد از تمرین"),
    ("میان وعده", "میان‌وعده"),
    ("میان‌وعده", "میان‌وعده"),
    ("میانوعده", "میان‌وعده"),
    ("صبحانه", "صبحانه"),
    ("ناهار", "ناهار"),
    ("نهار", "ناهار"),
    ("عصرانه", "عصرانه"),
    ("شام", "شام"),
]
RE_MEAL = re.compile(r"(?<![\w؀-ۿ])(" + "|".join(re.escape(k) for k, _ in MEALS) + r")(?![\w؀-ۿ])")
_H = r"(\d{1,2})(?:[:٫](\d{2})|\.(5))?"  # 8, 8:30, 10.5 («ده و نیم»)
_PART = r"(صبح|ظهر|بعدازظهر|بعد از ظهر|عصر|شب)"
RE_TIME_PART = re.compile(r"(?:ساعت\s*)?" + _H + r"\s*" + _PART)
RE_TIME_PLAIN = re.compile(r"ساعت\s*" + _H + r"(?![\d])")


@dataclass
class ParsedMeal:
    title: str
    time_text: str | None
    content: str
    notes: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class ParsedNutrition:
    meals: list[ParsedMeal]
    notes: str | None
    warnings: list[str]
    text: str
    program_type: str = "nutrition"

    def to_dict(self) -> dict:
        return asdict(self)


def _time(m: re.Match, with_part: bool) -> str:
    h = int(m.group(1))
    mi = int(m.group(2)) if m.group(2) else (30 if m.group(3) else 0)
    if with_part:
        part = m.group(4)
        if part == "ظهر" and h <= 5:
            h += 12
        elif part in ("بعدازظهر", "بعد از ظهر", "عصر", "شب") and h < 12:
            h += 12
    return f"{h:02d}:{mi:02d}"


def _clean(text: str) -> str:
    text = re.sub(r"^[\s،,.:؛-]+|[\s،,؛:-]+$", "", text)
    return to_persian_digits(re.sub(r"\s+", " ", text)).strip()


def parse_nutrition(text: str) -> ParsedNutrition:
    normalized = words_to_digits(text)
    marks = list(RE_MEAL.finditer(normalized))
    warnings: list[str] = []
    meals: list[ParsedMeal] = []
    preamble = normalized[: marks[0].start()] if marks else ""
    if not marks:
        warnings.append("نام وعده‌ای (صبحانه، ناهار، ...) تشخیص داده نشد؛ کل متن در یک وعده آمد")
        marks_iter = [(None, 0, len(normalized))]
    else:
        marks_iter = [
            (m.group(1), m.end(), marks[i + 1].start() if i + 1 < len(marks) else len(normalized))
            for i, m in enumerate(marks)
        ]
    labels = dict(MEALS)
    for key, start, end in marks_iter:
        body = normalized[start:end]
        time_text = None
        tm, with_part = RE_TIME_PART.search(body), True
        if not tm:
            tm, with_part = RE_TIME_PLAIN.search(body), False
        if tm:
            time_text = to_persian_digits(_time(tm, with_part))
            body = body[: tm.start()] + " " + body[tm.end() :]
        content = _clean(body)
        meal = ParsedMeal(title=labels.get(key, "وعده"), time_text=time_text, content=content)
        if not content:
            meal.warnings.append("محتوای این وعده گفته نشده")
        meals.append(meal)
    return ParsedNutrition(meals=meals, notes=_clean(preamble) or None, warnings=warnings, text=text.strip())
