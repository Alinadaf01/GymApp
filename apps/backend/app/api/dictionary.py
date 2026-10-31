import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import ExerciseDictionaryEntry, User
from app.parsers.dictionary import key
from app.services.activity import log_activity
from app.services.text import normalize_letters

router = APIRouter(prefix="/exercises/dictionary", tags=["dictionary"], dependencies=[Depends(get_current_user)])


class EntryIn(BaseModel):
    canonical_name: str = Field(min_length=1, max_length=200)
    aliases: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("canonical_name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = normalize_letters(v)
        if not v:
            raise ValueError("نام حرکت الزامی است.")
        return v

    @field_validator("aliases")
    @classmethod
    def _aliases(cls, v: list[str]) -> list[str]:
        out, seen = [], set()
        for a in v:
            a = normalize_letters(a)[:200]
            if a and key(a) not in seen:
                seen.add(key(a))
                out.append(a)
        return out


class EntryOut(BaseModel):
    id: uuid.UUID
    canonical_name: str
    aliases: list[str]


def _out(e: ExerciseDictionaryEntry) -> EntryOut:
    return EntryOut(id=e.id, canonical_name=e.canonical_name, aliases=list(e.aliases or []))


def _check_conflicts(db: Session, body: EntryIn, own_id: uuid.UUID | None) -> None:
    """A spoken form must map to exactly one exercise."""
    mine = {key(body.canonical_name), *(key(a) for a in body.aliases)}
    for other in db.scalars(select(ExerciseDictionaryEntry)):
        if other.id == own_id:
            continue
        theirs = {key(other.canonical_name), *(key(a) for a in other.aliases or [])}
        clash = mine & theirs
        if clash:
            raise HTTPException(
                status.HTTP_409_CONFLICT, f"این نام یا مترادف قبلاً برای «{other.canonical_name}» ثبت شده است."
            )


@router.get("", response_model=list[EntryOut])
def list_entries(q: str | None = Query(default=None, max_length=100), db: Session = Depends(get_db)):
    entries = db.scalars(select(ExerciseDictionaryEntry).order_by(ExerciseDictionaryEntry.canonical_name)).all()
    if q and q.strip():
        k = key(q)
        entries = [e for e in entries if k in key(e.canonical_name) or any(k in key(a) for a in e.aliases or [])]
    return [_out(e) for e in entries]


@router.post("", response_model=EntryOut, status_code=201)
def create_entry(body: EntryIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _check_conflicts(db, body, None)
    entry = ExerciseDictionaryEntry(canonical_name=body.canonical_name, aliases=body.aliases)
    db.add(entry)
    db.flush()
    log_activity(db, action="dictionary.created", entity_type="exercise_dictionary", entity_id=entry.id,
                 actor_user_id=user.id, meta={"name": entry.canonical_name})
    db.commit()
    return _out(entry)


@router.put("/{entry_id}", response_model=EntryOut)
def update_entry(entry_id: uuid.UUID, body: EntryIn, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    entry = db.get(ExerciseDictionaryEntry, entry_id)
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "مورد پیدا نشد.")
    _check_conflicts(db, body, entry.id)
    entry.canonical_name, entry.aliases = body.canonical_name, body.aliases
    db.commit()
    return _out(entry)


@router.delete("/{entry_id}", status_code=204)
def delete_entry(entry_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    entry = db.get(ExerciseDictionaryEntry, entry_id)
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "مورد پیدا نشد.")
    db.delete(entry)
    db.commit()
    return Response(status_code=204)
