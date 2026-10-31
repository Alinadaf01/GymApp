"""Single entry point: (text, program type) -> parsed payload (JSON-safe dict),
and parsed payload -> program content for the database."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ExerciseDictionaryEntry
from app.parsers.dictionary import Entry, ExerciseDictionary
from app.parsers.nutrition import parse_nutrition
from app.parsers.supplements import parse_supplements
from app.parsers.workout import parse_workout


def load_dictionary(db: Session) -> ExerciseDictionary:
    rows = db.scalars(select(ExerciseDictionaryEntry)).all()
    return ExerciseDictionary([Entry(r.canonical_name, tuple(r.aliases or ())) for r in rows])


def parse_text(text: str, program_type: str, dictionary: ExerciseDictionary, session_title: str | None = None) -> dict:
    if program_type == "workout":
        return parse_workout(text, dictionary, session_title=session_title).to_dict()
    if program_type == "nutrition":
        return parse_nutrition(text).to_dict()
    return parse_supplements(text, program_type).to_dict()


EXERCISE_FIELDS = (
    "name", "execution_type", "sets", "reps", "weight_value", "weight_unit", "duration_seconds",
    "distance_value", "distance_unit", "rest_seconds", "notes", "raw_text",
)


def session_from_payload(payload: dict, fallback_title: str) -> dict:
    """Parsed workout -> one SessionWrite-compatible dict."""
    return {
        "title": payload.get("session_title") or fallback_title,
        "notes": payload.get("session_notes"),
        "exercises": [{k: e.get(k) for k in EXERCISE_FIELDS} for e in payload.get("exercises", [])],
    }


def meals_from_payload(payload: dict) -> list[dict]:
    return [
        {"title": m["title"], "time_text": m.get("time_text"), "content": m["content"], "notes": m.get("notes")}
        for m in payload.get("meals", [])
        if m.get("content")
    ]


def supplements_from_payload(payload: dict) -> list[dict]:
    return [
        {"name": x["name"], "amount_text": x.get("amount_text"), "timing_text": x.get("timing_text"),
         "notes": x.get("notes")}
        for x in payload.get("supplements", [])
    ]
