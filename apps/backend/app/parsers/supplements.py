"""Supplement/vitamin voice text -> items. Only what the coach said is stored;
no dosage is inferred or suggested (spec §6.4)."""
import re
from dataclasses import asdict, dataclass, field

from app.parsers.numbers import words_to_digits
from app.services.text import to_persian_digits

N = r"(\d+(?:\.\d+)?)"
AMOUNT_UNITS = r"(عدد|تا|قرص|کپسول|اسکوپ|پیمانه|قاشق(?:\s*(?:غذاخوری|چای\s*خوری|مرباخوری))?|گرم|میلی\s*گرم|میلی‌گرم|میکروگرم|واحد|سی\s*سی|میلی\s*لیتر|لیوان|ساشه|قطره)"
RE_AMOUNT = re.compile(N + r"\s*" + AMOUNT_UNITS + r"(?![\w\u200c])")
RE_FREQ = re.compile(r"(روزی|هفته‌ای|هفته ای|هر روز|یک روز در میان)\s*(?:" + N + r"\s*(?:بار|وعده))?")
TIMINGS = [
    r"قبل\s+از\s+خواب", r"قبل\s+(?:از\s+)?تمرین", r"بعد\s+(?:از\s+)?تمرین", r"حین\s+تمرین",
    r"(?:قبل|بعد)\s+از\s+(?:صبحانه|ناهار|نهار|شام|غذا|وعده)", r"همراه\s+(?:با\s+)?(?:صبحانه|ناهار|نهار|شام|غذا|وعده)",
    r"با\s+معده\s+خالی", r"ناشتا", r"صبح(?:ها)?", r"ظهر", r"عصر", r"شب(?:ها)?",
]
RE_TIMING = re.compile(r"(?<![\w\u200c])(" + "|".join(TIMINGS) + r")(?![\w\u200c])")
SPLIT = re.compile(r"[،,.;؛\n]+|\s(?:بعدی|بعد\s+هم|و\s+بعد|همچنین)\s")


@dataclass
class ParsedSupplement:
    name: str
    amount_text: str | None
    timing_text: str | None
    notes: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class ParsedSupplements:
    supplements: list[ParsedSupplement]
    notes: str | None
    warnings: list[str]
    text: str
    program_type: str = "supplement"

    def to_dict(self) -> dict:
        return asdict(self)


def _fa(s: str | None) -> str | None:
    return to_persian_digits(re.sub(r"\s+", " ", s).strip()) if s and s.strip() else None


def parse_supplements(text: str, program_type: str = "supplement") -> ParsedSupplements:
    normalized = words_to_digits(text)
    items: list[ParsedSupplement] = []
    notes: list[str] = []
    for seg in (s.strip() for s in SPLIT.split(normalized) if s and s.strip()):
        rest = seg
        amount = timing = None
        parts = []
        if m := RE_AMOUNT.search(rest):
            amount = f"{m.group(1)} {'عدد' if m.group(2) == 'تا' else m.group(2)}"
            rest = rest[: m.start()] + " " + rest[m.end() :]
        if m := RE_FREQ.search(rest):
            parts.append(m.group(0))
            rest = rest[: m.start()] + " " + rest[m.end() :]
        timings = []
        while m := RE_TIMING.search(rest):
            timings.append(m.group(1))
            rest = rest[: m.start()] + " " + rest[m.end() :]
        if timings or parts:
            timing = "، ".join(parts + timings)
        name = re.sub(r"(^|\s)(مصرف|بخوره|بخور|بخورد|کنه|کند|شود|بشه|میل|هم|و)(?=\s|$)", " ", rest)
        name = re.sub(r"\s+", " ", name).strip(" ،,-")
        if not name:
            if amount or timing:
                notes.append(seg)
            continue
        item = ParsedSupplement(name=_fa(name), amount_text=_fa(amount), timing_text=_fa(timing))
        if not amount:
            item.warnings.append("مقدار گفته نشده")
        if not timing:
            item.warnings.append("زمان مصرف گفته نشده")
        items.append(item)
    warnings = [] if items else ["هیچ قلمی تشخیص داده نشد؛ متن را بررسی و اصلاح کنید"]
    if notes:
        warnings.append("بخشی از متن بدون نام قلم بود: " + "، ".join(_fa(n) for n in notes))
    return ParsedSupplements(
        supplements=items, notes=None, warnings=warnings, text=text.strip(), program_type=program_type
    )
