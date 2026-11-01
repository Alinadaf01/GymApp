"""Persian number words -> ASCII digits, inside free text.

    «چهار ست پونزده تایی» -> «4 ست 15 تایی»
    «بیست و پنج کیلو»     -> «25 کیلو»
    «یک و نیم دقیقه»       -> «1.5 دقیقه»
"""
import re

from app.services.text import normalize_letters, to_ascii_digits

ZWNJ = "‌"

UNITS = {
    "صفر": 0, "یک": 1, "یه": 1, "دو": 2, "سه": 3, "چهار": 4, "چار": 4, "پنج": 5, "شش": 6, "شیش": 6,
    "هفت": 7, "هشت": 8, "نه": 9,
}
TEENS = {
    "ده": 10, "یازده": 11, "دوازده": 12, "سیزده": 13, "چهارده": 14, "چارده": 14, "پانزده": 15, "پونزده": 15,
    "شانزده": 16, "شونزده": 16, "هفده": 17, "هیفده": 17, "هجده": 18, "هیجده": 18, "نوزده": 19,
    # Spoken forms with the final «د» dropped, as Whisper writes them («دوازه تکرار»)
    "یازه": 11, "دوازه": 12, "سیزه": 13, "پونزه": 15, "پانزه": 15, "شونزه": 16,
    "شانزه": 16, "هیفه": 17, "هیجه": 18, "نوزه": 19, "دوزده": 12, "دوزه": 12,
}
TENS = {"بیست": 20, "سی": 30, "چهل": 40, "پنجاه": 50, "شصت": 60, "هفتاد": 70, "هشتاد": 80, "نود": 90}
HUNDREDS = {
    "صد": 100, "یکصد": 100, "دویست": 200, "سیصد": 300, "چهارصد": 400, "پانصد": 500, "پونصد": 500,
    "ششصد": 600, "هفتصد": 700, "هشتصد": 800, "نهصد": 900,
}
WORDS = {**UNITS, **TEENS, **TENS, **HUNDREDS}

# Words that commonly follow a number in coaching speech
UNIT_WORDS = {
    "ست", "ستی", "تا", "تایی", "تکرار", "کیلو", "کیلویی", "کیلوگرم", "کیلوگرمی", "پوند", "ثانیه", "ثانیه‌ای",
    "دقیقه", "دقیقه‌ای", "متر", "کیلومتر", "عدد", "قرص", "کپسول", "اسکوپ", "پیمانه", "قاشق", "گرم", "واحد",
    "بار", "لیوان", "کف", "برش", "تکه", "ساعت", "نیم",
}
DAY_PARTS = {"صبح", "ظهر", "عصر", "شب", "بعدازظهر"}
# Suffixes glued to a number word with ZWNJ: «پانزده‌تایی», «دوازده‌تا»
GLUED_SUFFIXES = ("تایی", "تا", "ستی", "ست", "کیلویی", "کیلو", "ای")

_TOKEN = re.compile(r"\S+")

COUNT_UNITS = {"ست", "ستی", "تکرار", "تایی", "تا", "تکراری"}

# Whisper often moves the «د/ت» of the number onto the next word:
# «دوازده تکرار» -> «دوزت ایکرار», «چهارده تکرار» -> «چاردت ایکرار».
_RE_SPLIT_TEKRAR = re.compile(r"(\S+?)ت\s+(?:ای|ا|ی)کرار(?!\w)")
_RE_TEKRAR_VARIANT = re.compile(r"(?<!\w)(?:ایکرار|اکرار|تیکرار|تکرا|تکرارو)(?!\w)")
# «چار، ست» — a pause after the number became a comma
_RE_NUM_COMMA_UNIT = re.compile(r"(\d+(?:\.\d+)?)\s*[،,]\s*(ست|ستی|تکرار|تایی)(?!\w)")


# Mis-heard numbers, accepted ONLY right before ست/تکرار/تایی («پین ست» = «پنج ست»)
MISHEARD_BEFORE_UNIT = {"پین": "پنج", "پنش": "پنج", "پن": "پنج", "هف": "هفت", "هش": "هشت", "شیس": "شیش"}


def _number_before_unit(token: str) -> str | None:
    """A clipped number word right before «ست/تکرار/تایی» («چارد» -> «چارده»)."""
    if token in MISHEARD_BEFORE_UNIT:
        return MISHEARD_BEFORE_UNIT[token]
    if len(token) < 3:
        return None
    for cand in (token + "ه", token + "ده", token[:-1] + "ه" if token.endswith("د") else ""):
        if cand in WORDS:
            return cand
    return None


# «سه ست» heard as one word. «سست» is never meant literally in a prescription.
GLUED_SET_WORDS = {"سست": ["سه", "ست"], "سهست": ["سه", "ست"]}


def _split_glued(token: str) -> list[str]:
    if token in GLUED_SET_WORDS:
        return list(GLUED_SET_WORDS[token])
    if token.endswith("ست") and token != "دوست" and token[:-2] in WORDS and token[:-2] != "نه":
        return [token[:-2], "ست"]  # «چهارست», «پنجست»
    if ZWNJ in token:
        head, _, tail = token.partition(ZWNJ)
        if head in WORDS and tail in GLUED_SUFFIXES:
            return [head, tail]
    for suffix in ("تایی", "تا"):
        # «پونزدهتایی» (no separator) — only when the prefix is a number word
        if token.endswith(suffix) and token[: -len(suffix)] in WORDS:
            return [token[: -len(suffix)], suffix]
    if re.fullmatch(r"\d+(?:\.\d+)?(تایی|تا|کیلویی|کیلو|ستی)", token):
        m = re.fullmatch(r"(\d+(?:\.\d+)?)(\D+)", token)
        return [m.group(1), m.group(2)]
    return [token]


def _is_number_word(tokens: list[str], i: int) -> bool:
    t = tokens[i]
    if t not in WORDS:
        return False
    if t == "نه":  # «نه» is also "no": a number only in a clear numeric context
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
        prev = tokens[i - 1] if i > 0 else ""
        return nxt in UNIT_WORDS or nxt in DAY_PARTS or prev == "ساعت"
    return True


def _read_number(tokens: list[str], i: int) -> tuple[float, int] | None:
    """Read a compound number starting at i. Returns (value, next_index)."""
    if tokens[i] == "هزار":  # bare «هزار» = 1000 («هزار واحد»)
        rest = _read_number(tokens, i + 2) if i + 2 < len(tokens) and tokens[i + 1] == "و" else None
        if rest:
            return 1000 + rest[0], rest[1]
        return 1000.0, i + 1
    if not _is_number_word(tokens, i) and not re.fullmatch(r"\d+(?:\.\d+)?", tokens[i]):
        return None
    total = 0.0
    current = 0.0
    j = i
    last_was_number = False
    while j < len(tokens):
        t = tokens[j]
        if re.fullmatch(r"\d+(?:\.\d+)?", t) and not last_was_number:
            current += float(t)
            last_was_number = True
            j += 1
        elif t in WORDS and _is_number_word(tokens, j) and not last_was_number:
            current += WORDS[t]
            last_was_number = True
            j += 1
        elif t == "هزار" and last_was_number:
            total += (current or 1) * 1000
            current = 0
            j += 1
        elif t == "و" and last_was_number and j + 1 < len(tokens):
            nxt = tokens[j + 1]
            if nxt == "نیم":
                current += 0.5
                j += 2
            elif (nxt in WORDS and _is_number_word(tokens, j + 1)) or re.fullmatch(r"\d+", nxt):
                last_was_number = False
                j += 1
            else:
                break
        else:
            break
    if j == i:
        return None
    return total + current, j


def _fmt(value: float) -> str:
    return str(int(value)) if value == int(value) else str(value)


def words_to_digits(text: str) -> str:
    """Normalize letters/digits and replace Persian number words with ASCII digits."""
    text = to_ascii_digits(normalize_letters(text))
    text = text.replace("٫", ".")
    text = _RE_SPLIT_TEKRAR.sub(r"\1 تکرار", text)
    text = _RE_TEKRAR_VARIANT.sub("تکرار", text)
    text = re.sub(r"(?<=\d)[,،](?=\d{3}\b)", "", text)  # 1,000 -> 1000
    out: list[str] = []
    tokens: list[str] = []
    for tok in _TOKEN.findall(text):
        # Keep punctuation as separate tokens so «تایی،» still matches
        m = re.fullmatch(r"(.*?)([،,.;:!?؛]*)", tok)
        core, punct = m.group(1), m.group(2)
        if core:
            tokens.extend(_split_glued(core))
        if punct:
            tokens.append(punct)
    # «دوست» is «دو ست» only when a count follows («دوست 12 تکرار», «دوست دوازده تایی»)
    for k in range(len(tokens) - 1, -1, -1):
        if tokens[k] == "دوست" and k + 1 < len(tokens) and (
            re.fullmatch(r"\d+(?:\.\d+)?", tokens[k + 1]) or tokens[k + 1] in WORDS
        ):
            tokens[k : k + 1] = ["دو", "ست"]
    for k in range(len(tokens) - 1):
        if tokens[k + 1] in COUNT_UNITS and tokens[k] not in WORDS:
            fixed = _number_before_unit(tokens[k])
            if fixed:
                tokens[k] = fixed
    i = 0
    while i < len(tokens):
        if tokens[i] == "نیم" and i + 1 < len(tokens) and tokens[i + 1] in UNIT_WORDS:
            out.append("0.5")
            i += 1
            continue
        read = _read_number(tokens, i)
        if read:
            value, i = read
            out.append(_fmt(value))
        else:
            out.append(tokens[i])
            i += 1
    joined = re.sub(r"\s+([،,.;:!?؛])", r"\1", " ".join(out))
    return _RE_NUM_COMMA_UNIT.sub(r"\1 \2", joined)
