import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.auth.sessions import now_utc
from app.models import Exercise, GeneratedPdf, NutritionMeal, Program, Student, Supplement, WorkoutSession
from app.models.enums import ProgramStatus, ProgramType
from app.schemas.program import (
    ExerciseOut,
    MealOut,
    PdfOut,
    ProgramContent,
    ProgramOut,
    SessionOut,
    StudentRef,
    SupplementOut,
)
from app.services.students import full_name

WORKOUT = {ProgramType.workout}
NUTRITION = {ProgramType.nutrition}
SUPPLEMENTS = {ProgramType.supplement, ProgramType.vitamin}

PROGRAM_NOT_FOUND = "برنامه پیدا نشد."
ARCHIVED_LOCKED = "برنامه بایگانی‌شده قابل ویرایش نیست. از آن کپی بگیرید."


def load_program(db: Session, program_id: uuid.UUID, *, for_update: bool = False) -> Program:
    stmt = (
        select(Program)
        .where(Program.id == program_id)
        .options(
            selectinload(Program.sessions).selectinload(WorkoutSession.exercises),
            selectinload(Program.meals),
            selectinload(Program.supplements),
        )
    )
    if for_update:
        stmt = stmt.with_for_update(of=Program)
    program = db.scalar(stmt)
    if program is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, PROGRAM_NOT_FOUND)
    return program


def assert_editable(program: Program) -> None:
    if program.status == ProgramStatus.archived:
        raise HTTPException(status.HTTP_409_CONFLICT, ARCHIVED_LOCKED)


def touch(program: Program) -> None:
    """Child edits must bump the program timestamp (used to detect outdated PDFs)."""
    # DB clock (same source as generated_pdfs.created_at)
    program.updated_at = func.now()


def validate_content_for_type(program_type: ProgramType, content: ProgramContent) -> None:
    errors = []
    if content.sessions and program_type not in WORKOUT:
        errors.append("جلسه و حرکت فقط برای برنامه تمرینی مجاز است.")
    if content.meals and program_type not in NUTRITION:
        errors.append("وعده غذایی فقط برای برنامه غذایی مجاز است.")
    if content.supplements and program_type not in SUPPLEMENTS:
        errors.append("اقلام مکمل/ویتامین فقط برای برنامه مکمل یا ویتامین مجاز است.")
    if errors:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, " ".join(errors))


def replace_content(program: Program, content: ProgramContent) -> None:
    """Replace all children; list order becomes sort_order."""
    program.sessions.clear()
    program.meals.clear()
    program.supplements.clear()
    for si, s in enumerate(content.sessions):
        session = WorkoutSession(title=s.title, notes=s.notes, sort_order=si)
        for ei, e in enumerate(s.exercises):
            session.exercises.append(Exercise(**e.model_dump(), sort_order=ei))
        program.sessions.append(session)
    for mi, m in enumerate(content.meals):
        program.meals.append(NutritionMeal(**m.model_dump(), sort_order=mi))
    for i, item in enumerate(content.supplements):
        program.supplements.append(Supplement(**item.model_dump(), sort_order=i))


def content_problem(program: Program) -> str | None:
    """Why a program cannot be approved yet (None if it can)."""
    if program.program_type in WORKOUT:
        if not program.sessions:
            return "برنامه تمرینی حداقل یک جلسه لازم دارد."
        if any(not s.exercises for s in program.sessions):
            return "هر جلسه باید حداقل یک حرکت داشته باشد."
    elif program.program_type in NUTRITION:
        if not program.meals:
            return "برنامه غذایی حداقل یک وعده لازم دارد."
    elif not program.supplements:
        return "این برنامه حداقل یک قلم لازم دارد."
    return None


def next_period_number(db: Session, student_id: uuid.UUID, program_type: ProgramType) -> int:
    current = db.scalar(
        select(func.max(Program.period_number)).where(
            Program.student_id == student_id, Program.program_type == program_type
        )
    )
    return (current or 0) + 1


def copy_program(db: Session, source: Program) -> Program:
    """New draft with copied content: new ids, new dates, next period. Source is untouched."""
    copy = Program(
        student_id=source.student_id,
        title=source.title,
        program_type=source.program_type,
        period_number=next_period_number(db, source.student_id, source.program_type),
        start_date=None,
        end_date=None,
        status=ProgramStatus.draft,
        notes=source.notes,
    )
    content = ProgramContent(
        sessions=[
            {
                "title": s.title,
                "notes": s.notes,
                "exercises": [
                    {
                        k: getattr(e, k)
                        for k in (
                            "name", "execution_type", "sets", "reps", "weight_value", "weight_unit",
                            "duration_seconds", "distance_value", "distance_unit", "rest_seconds", "notes",
                            "raw_text",
                        )
                    }
                    for e in s.exercises
                ],
            }
            for s in source.sessions
        ],
        meals=[
            {"title": m.title, "time_text": m.time_text, "content": m.content, "notes": m.notes} for m in source.meals
        ],
        supplements=[
            {"name": x.name, "amount_text": x.amount_text, "timing_text": x.timing_text, "notes": x.notes}
            for x in source.supplements
        ],
    )
    replace_content(copy, content)
    db.add(copy)
    db.flush()
    return copy


def pdf_out(pdf: GeneratedPdf, program_updated_at: datetime) -> PdfOut:
    return PdfOut(
        id=pdf.id,
        program_id=pdf.program_id,
        version=pdf.version,
        created_at=pdf.created_at,
        is_outdated=pdf.created_at < program_updated_at,
    )


def to_out(db: Session, program: Program) -> ProgramOut:
    student = db.get(Student, program.student_id)
    latest = db.scalar(
        select(GeneratedPdf)
        .where(GeneratedPdf.program_id == program.id)
        .order_by(GeneratedPdf.version.desc())
        .limit(1)
    )
    return ProgramOut(
        id=program.id,
        student=StudentRef(id=student.id, full_name=full_name(student)),
        title=program.title,
        program_type=program.program_type,
        period_number=program.period_number,
        start_date=program.start_date,
        end_date=program.end_date,
        status=program.status,
        notes=program.notes,
        source_voice_record_id=program.source_voice_record_id,
        created_at=program.created_at,
        updated_at=program.updated_at,
        approved_at=program.approved_at,
        sessions=[SessionOut.model_validate(s) for s in program.sessions],
        meals=[MealOut.model_validate(m) for m in program.meals],
        supplements=[SupplementOut.model_validate(x) for x in program.supplements],
        latest_pdf=pdf_out(latest, program.updated_at) if latest else None,
    )
