"""Persian text helpers shared by search, validation and (later) the voice parser."""
import re

_DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
# Arabic forms that commonly appear from keyboards/OCR -> Persian forms
_CHAR_MAP = str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک", "ۀ": "ه", "ة": "ه"})
_SPACES = re.compile(r"\s+")


def to_ascii_digits(value: str) -> str:
    return value.translate(_DIGIT_MAP)


def normalize_persian(value: str) -> str:
    """Unify Arabic/Persian letters, digits and whitespace. Does not change meaning."""
    value = value.translate(_CHAR_MAP)
    value = to_ascii_digits(value)
    return _SPACES.sub(" ", value).strip()


def normalize_phone(value: str) -> str:
    """Keep digits and a leading '+', e.g. '۰۹۱۲-۱۲۳ ۴۵۶۷' -> '09121234567'."""
    value = to_ascii_digits(value).strip()
    plus = value.startswith("+")
    digits = re.sub(r"\D", "", value)
    return f"+{digits}" if plus else digits


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
