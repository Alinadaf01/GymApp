"""Exercise-name matching against the coach-managed dictionary.

- Exact match (ignoring spaces / ZWNJ / Arabic letter forms) -> canonical name.
- Otherwise the raw name is KEPT unchanged; a close dictionary entry is only
  offered as a suggestion for the coach to confirm (never auto-replaced).
"""
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.services.text import normalize_letters


def key(text: str) -> str:
    return normalize_letters(text).replace("‌", "").replace(" ", "")


@dataclass(frozen=True)
class Entry:
    canonical: str
    aliases: tuple[str, ...] = ()


@dataclass
class Match:
    name: str  # name to use (canonical on exact match, raw otherwise)
    matched: bool
    consumed_words: int  # how many leading words formed the name
    suggestion: str | None = None


class ExerciseDictionary:
    def __init__(self, entries: list[Entry]):
        self._by_key: dict[str, str] = {}
        for e in entries:
            for form in (e.canonical, *e.aliases):
                self._by_key.setdefault(key(form), e.canonical)
        self._canonicals = sorted({e.canonical for e in entries})

    def __len__(self) -> int:
        return len(self._canonicals)

    @property
    def canonical_names(self) -> list[str]:
        return list(self._canonicals)

    def match_prefix(self, words: list[str]) -> Match | None:
        """Longest run of leading words that is exactly a dictionary name/alias."""
        for n in range(len(words), 0, -1):
            canonical = self._by_key.get(key(" ".join(words[:n])))
            if canonical:
                return Match(name=canonical, matched=True, consumed_words=n)
        return None

    def suggest(self, name: str, threshold: float = 0.75) -> str | None:
        k = key(name)
        if not k:
            return None
        best, best_score = None, 0.0
        for form_key, canonical in self._by_key.items():
            score = SequenceMatcher(None, k, form_key).ratio()
            if score > best_score:
                best, best_score = canonical, score
        return best if best_score >= threshold and best != name else None


EMPTY = ExerciseDictionary([])
