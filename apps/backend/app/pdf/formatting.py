"""Display helpers for printed programs: Persian digits, Jalali dates, units.

Values are shown exactly as the coach entered them — only formatting changes
(e.g. 60 seconds -> «۱ دقیقه»), never the meaning. Missing values print «—».
"""
from datetime import date, datetime
from decimal import Decimal

import jdatetime

from app.services.dates import local_tz

_FA = str.maketrans("0123456789.", "۰۱۲۳۴۵۶۷۸۹٫")
DASH = "—"

UNIT_LABELS = {"kg": "کیلوگرم", "lb": "پوند", "m": "متر", "km": "کیلومتر"}


def fa(value) -> str:
    if value is None or value == "":
        return DASH
    return str(value).translate(_FA)


def number(value: Decimal | int | float | None) -> str:
    if value is None:
        return DASH
    text = format(Decimal(str(value)), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return fa(text)


def jalali(value: date | datetime | None) -> str:
    if value is None:
        return DASH
    if isinstance(value, datetime):
        value = value.astimezone(local_tz()).date()
    j = jdatetime.date.fromgregorian(date=value)
    return fa(f"{j.year}/{j.month:02d}/{j.day:02d}")


def seconds(value: int | None) -> str:
    if value is None:
        return DASH
    minutes, secs = divmod(value, 60)
    if minutes and secs:
        return f"{fa(minutes)} دقیقه و {fa(secs)} ثانیه"
    if minutes:
        return f"{fa(minutes)} دقیقه"
    return f"{fa(secs)} ثانیه"


def with_unit(value, unit: str | None) -> str:
    if value is None:
        return DASH
    label = UNIT_LABELS.get(unit or "", unit or "")
    return f"{number(value)} {label}".strip()
