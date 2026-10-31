import hashlib
import uuid
from collections.abc import Iterable

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session

from app.models import Program, Student
from app.models.enums import ProgramStatus
from app.schemas.student import LastProgram, StudentListItem, StudentOut
from app.services.text import escape_like, normalize_persian, normalize_phone


def full_name(s: Student) -> str:
    return f"{s.first_name} {s.last_name}"


def photo_url(s: Student) -> str | None:
    if not s.profile_photo_path:
        return None
    # Version param changes whenever the file changes (cache busting); not a credential
    v = hashlib.sha256(s.profile_photo_path.encode()).hexdigest()[:12]
    return f"/api/students/{s.id}/profile-photo?v={v}"


def last_programs(db: Session, student_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, LastProgram]:
    """Latest non-draft program per student (one query, DISTINCT ON)."""
    ids = list(student_ids)
    if not ids:
        return {}
    when = func.coalesce(Program.approved_at, Program.created_at)
    rows = db.execute(
        select(Program, when.label("when"))
        .where(Program.student_id.in_(ids), Program.status != ProgramStatus.draft)
        .order_by(Program.student_id, when.desc())
        .distinct(Program.student_id)
    ).all()
    return {
        p.student_id: LastProgram(id=p.id, title=p.title, program_type=p.program_type, status=p.status, date=w)
        for p, w in rows
    }


def search_filter(q: str):
    """Every whitespace-separated term must match first name, last name or phone."""
    conds = []
    for term in normalize_persian(q).split(" ")[:5]:
        if not term:
            continue
        like = f"%{escape_like(term)}%"
        options = [Student.first_name.ilike(like, escape="\\"), Student.last_name.ilike(like, escape="\\")]
        digits = normalize_phone(term).lstrip("+")
        if digits:
            options.append(Student.phone.ilike(f"%{escape_like(digits)}%", escape="\\"))
        conds.append(or_(*options))
    return and_(*conds) if conds else None


def apply_search(stmt: Select, q: str | None) -> Select:
    if q and q.strip():
        cond = search_filter(q)
        if cond is not None:
            stmt = stmt.where(cond)
    return stmt


def to_out(db: Session, s: Student) -> StudentOut:
    last = last_programs(db, [s.id]).get(s.id)
    return StudentOut(
        id=s.id,
        first_name=s.first_name,
        last_name=s.last_name,
        full_name=full_name(s),
        phone=s.phone,
        birth_date=s.birth_date,
        gender=s.gender,
        height_cm=s.height_cm,
        initial_weight_kg=s.initial_weight_kg,
        current_weight_kg=s.current_weight_kg,
        training_history=s.training_history,
        goal=s.goal,
        limitations_notes=s.limitations_notes,
        start_date=s.start_date,
        coach_notes=s.coach_notes,
        status=s.status,
        profile_photo_url=photo_url(s),
        photo_consent_at=s.photo_consent_at,
        created_at=s.created_at,
        updated_at=s.updated_at,
        archived_at=s.archived_at,
        last_program=last,
    )


def to_list_items(db: Session, students: list[Student]) -> list[StudentListItem]:
    lasts = last_programs(db, (s.id for s in students))
    return [
        StudentListItem(
            id=s.id,
            full_name=full_name(s),
            first_name=s.first_name,
            last_name=s.last_name,
            phone=s.phone,
            current_weight_kg=s.current_weight_kg,
            start_date=s.start_date,
            status=s.status,
            profile_photo_url=photo_url(s),
            last_program=lasts.get(s.id),
            created_at=s.created_at,
        )
        for s in students
    ]
