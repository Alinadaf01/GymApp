import re
import uuid
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.students import get_student_or_404
from app.auth.dependencies import get_current_user
from app.auth.sessions import now_utc
from app.database import get_db
from app.models import Exercise, GeneratedPdf, NutritionMeal, Program, Student, Supplement, User, WorkoutSession
from app.models.enums import ProgramStatus, ProgramType, StudentStatus
from app.pdf.service import generate_pdf
from app.schemas.program import (
    ExerciseCreate,
    ExerciseOut,
    ExerciseWrite,
    MealCreate,
    MealOut,
    MealWrite,
    NextPeriodOut,
    PdfOut,
    ProgramCreate,
    ProgramListItem,
    ProgramListResponse,
    ProgramOut,
    ProgramUpdate,
    SessionCreate,
    SessionOut,
    SessionUpdate,
    StudentRef,
    SupplementCreate,
    SupplementOut,
    SupplementWrite,
)
from app.services.activity import log_activity
from app.services.programs import (
    NUTRITION,
    SUPPLEMENTS,
    WORKOUT,
    assert_editable,
    content_problem,
    copy_program,
    load_program,
    next_period_number,
    pdf_out,
    replace_content,
    to_out,
    touch,
    validate_content_for_type,
)
from app.services.students import apply_search, full_name
from app.services.text import escape_like, normalize_letters, normalize_persian, to_persian_digits
from app.storage import files

router = APIRouter(tags=["programs"], dependencies=[Depends(get_current_user)])


def _log(db, user, action, program: Program, **meta):
    log_activity(
        db, action=action, entity_type="program", entity_id=program.id,
        student_id=program.student_id, actor_user_id=user.id, meta=meta or None,
    )


# ---- list / create -------------------------------------------------------------


class StatusFilter(str, Enum):
    current = "current"  # draft + approved
    draft = "draft"
    approved = "approved"
    archived = "archived"
    all = "all"


@router.get("/programs", response_model=ProgramListResponse)
def list_programs(
    q: str | None = Query(default=None, max_length=100),
    program_type: ProgramType | None = Query(default=None, alias="type"),
    status_filter: StatusFilter = Query(default=StatusFilter.current, alias="status"),
    student_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> ProgramListResponse:
    stmt = select(Program, Student).join(Student, Student.id == Program.student_id)
    if status_filter == StatusFilter.current:
        stmt = stmt.where(Program.status != ProgramStatus.archived)
    elif status_filter != StatusFilter.all:
        stmt = stmt.where(Program.status == ProgramStatus(status_filter.value))
    if program_type:
        stmt = stmt.where(Program.program_type == program_type)
    if student_id:
        stmt = stmt.where(Program.student_id == student_id)
    if q and q.strip():
        # Titles keep the digits as typed: match both Persian and ASCII digit forms
        forms = {normalize_letters(q), normalize_persian(q), to_persian_digits(normalize_letters(q))}
        matching_students = apply_search(select(Student.id), q)
        stmt = stmt.where(
            or_(
                *[Program.title.ilike(f"%{escape_like(f)}%", escape="\\") for f in forms],
                Program.student_id.in_(matching_students),
            )
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(
        stmt.order_by(Program.updated_at.desc(), Program.id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    counts = dict(
        db.execute(
            select(GeneratedPdf.program_id, func.count())
            .where(GeneratedPdf.program_id.in_([p.id for p, _ in rows]))
            .group_by(GeneratedPdf.program_id)
        ).all()
    )
    return ProgramListResponse(
        items=[
            ProgramListItem(
                id=p.id, student=StudentRef(id=s.id, full_name=full_name(s)), title=p.title,
                program_type=p.program_type, period_number=p.period_number, status=p.status,
                start_date=p.start_date, end_date=p.end_date, created_at=p.created_at,
                updated_at=p.updated_at, approved_at=p.approved_at, pdf_count=counts.get(p.id, 0),
            )
            for p, s in rows
        ],
        total=total, page=page, page_size=page_size,
    )


@router.get("/students/{student_id}/programs/next-period", response_model=NextPeriodOut)
def next_period(student_id: uuid.UUID, program_type: ProgramType = Query(alias="type"), db: Session = Depends(get_db)):
    get_student_or_404(db, student_id)
    return NextPeriodOut(period_number=next_period_number(db, student_id, program_type))


@router.post("/students/{student_id}/programs", response_model=ProgramOut, status_code=status.HTTP_201_CREATED)
def create_program(
    student_id: uuid.UUID, body: ProgramCreate, db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProgramOut:
    student = get_student_or_404(db, student_id)
    if student.status == StudentStatus.archived:
        raise HTTPException(status.HTTP_409_CONFLICT, "شاگرد بایگانی است. ابتدا او را از بایگانی خارج کنید.")
    validate_content_for_type(body.program_type, body)
    program = Program(
        student_id=student.id,
        title=body.title,
        program_type=body.program_type,
        period_number=body.period_number or next_period_number(db, student.id, body.program_type),
        start_date=body.start_date,
        end_date=body.end_date,
        notes=body.notes,
        status=ProgramStatus.draft,  # never final before explicit approval
    )
    replace_content(program, body)
    db.add(program)
    db.flush()
    _log(db, user, "program.created", program)
    db.commit()
    return to_out(db, load_program(db, program.id))


# ---- single program -----------------------------------------------------------------


@router.get("/programs/{program_id}", response_model=ProgramOut)
def get_program(program_id: uuid.UUID, db: Session = Depends(get_db)) -> ProgramOut:
    return to_out(db, load_program(db, program_id))


@router.put("/programs/{program_id}", response_model=ProgramOut)
def update_program(
    program_id: uuid.UUID, body: ProgramUpdate, db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProgramOut:
    program = load_program(db, program_id, for_update=True)
    assert_editable(program)
    validate_content_for_type(program.program_type, body)
    for field in ("title", "period_number", "start_date", "end_date", "notes"):
        setattr(program, field, getattr(body, field))
    replace_content(program, body)
    touch(program)
    if program.status == ProgramStatus.approved:
        # Draft saves are not history; edits to an approved program are
        _log(db, user, "program.updated", program)
    db.commit()
    db.expire_all()
    return to_out(db, load_program(db, program_id))


@router.delete("/programs/{program_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_draft(program_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Only drafts can be deleted. Approved programs are archived, never deleted."""
    program = load_program(db, program_id, for_update=True)
    if program.status != ProgramStatus.draft:
        raise HTTPException(status.HTTP_409_CONFLICT, "فقط پیش‌نویس قابل حذف است. برنامه تأییدشده را بایگانی کنید.")
    log_activity(
        db, action="program.draft_deleted", entity_type="program", entity_id=program.id,
        student_id=program.student_id, actor_user_id=user.id, meta={"title": program.title},
    )
    db.delete(program)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/programs/{program_id}/duplicate", response_model=ProgramOut, status_code=status.HTTP_201_CREATED)
def duplicate_program(program_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    source = load_program(db, program_id)
    copy = copy_program(db, source)
    _log(db, user, "program.duplicated", copy, source_id=str(source.id))
    db.commit()
    return to_out(db, load_program(db, copy.id))


@router.post("/programs/{program_id}/approve", response_model=ProgramOut)
def approve_program(program_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Idempotent: approving an approved program changes nothing and logs nothing."""
    program = load_program(db, program_id, for_update=True)
    if program.status == ProgramStatus.archived:
        raise HTTPException(status.HTTP_409_CONFLICT, "برنامه بایگانی‌شده قابل تأیید نیست.")
    if program.status == ProgramStatus.draft:
        problem = content_problem(program)
        if problem:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problem)
        program.status = ProgramStatus.approved
        program.approved_at = now_utc()
        _log(db, user, "program.approved", program)
        db.commit()
    return to_out(db, load_program(db, program_id))


@router.post("/programs/{program_id}/archive", response_model=ProgramOut)
def archive_program(program_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    program = load_program(db, program_id, for_update=True)
    if program.status != ProgramStatus.archived:
        program.status = ProgramStatus.archived
        _log(db, user, "program.archived", program)
        db.commit()
    return to_out(db, load_program(db, program_id))


# ---- granular content endpoints (spec §14) -----------------------------------------


def _editable_of_type(db: Session, program_id: uuid.UUID, allowed: set[ProgramType], label: str) -> Program:
    program = load_program(db, program_id, for_update=True)
    assert_editable(program)
    if program.program_type not in allowed:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{label} برای این نوع برنامه مجاز نیست.")
    return program


def _insert(items: list, item, position: int | None) -> None:
    items.insert(len(items) if position is None else min(position, len(items)), item)
    for i, x in enumerate(items):
        x.sort_order = i


def _get_child(db: Session, model, child_id: uuid.UUID, label: str):
    obj = db.get(model, child_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{label} پیدا نشد.")
    return obj


def _finish(db: Session, program: Program, user: User):
    touch(program)
    if program.status == ProgramStatus.approved:
        _log(db, user, "program.updated", program)
    db.commit()


@router.get("/programs/{program_id}/sessions", response_model=list[SessionOut])
def list_sessions(program_id: uuid.UUID, db: Session = Depends(get_db)):
    return [SessionOut.model_validate(s) for s in load_program(db, program_id).sessions]


@router.post("/programs/{program_id}/sessions", response_model=SessionOut, status_code=201)
def create_session(program_id: uuid.UUID, body: SessionCreate, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    program = _editable_of_type(db, program_id, WORKOUT, "جلسه")
    session = WorkoutSession(title=body.title, notes=body.notes, sort_order=0)
    for i, e in enumerate(body.exercises):
        session.exercises.append(Exercise(**e.model_dump(), sort_order=i))
    _insert(program.sessions, session, body.sort_order)
    _finish(db, program, user)
    db.refresh(session)
    return SessionOut.model_validate(session)


@router.put("/sessions/{session_id}", response_model=SessionOut)
def update_session(session_id: uuid.UUID, body: SessionUpdate, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    session = _get_child(db, WorkoutSession, session_id, "جلسه")
    program = _editable_of_type(db, session.program_id, WORKOUT, "جلسه")
    session.title, session.notes = body.title, body.notes
    if body.sort_order is not None:
        program.sessions.remove(session)
        _insert(program.sessions, session, body.sort_order)
    _finish(db, program, user)
    db.refresh(session)
    return SessionOut.model_validate(session)


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    session = _get_child(db, WorkoutSession, session_id, "جلسه")
    program = _editable_of_type(db, session.program_id, WORKOUT, "جلسه")
    program.sessions.remove(session)
    for i, s in enumerate(program.sessions):
        s.sort_order = i
    _finish(db, program, user)
    return Response(status_code=204)


@router.post("/sessions/{session_id}/exercises", response_model=ExerciseOut, status_code=201)
def create_exercise(session_id: uuid.UUID, body: ExerciseCreate, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    session = _get_child(db, WorkoutSession, session_id, "جلسه")
    program = _editable_of_type(db, session.program_id, WORKOUT, "حرکت")
    exercise = Exercise(**body.model_dump(exclude={"sort_order"}), sort_order=0)
    _insert(session.exercises, exercise, body.sort_order)
    _finish(db, program, user)
    db.refresh(exercise)
    return ExerciseOut.model_validate(exercise)


@router.put("/exercises/{exercise_id}", response_model=ExerciseOut)
def update_exercise(exercise_id: uuid.UUID, body: ExerciseWrite, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    exercise = _get_child(db, Exercise, exercise_id, "حرکت")
    session = db.get(WorkoutSession, exercise.session_id)
    program = _editable_of_type(db, session.program_id, WORKOUT, "حرکت")
    for k, v in body.model_dump().items():
        setattr(exercise, k, v)
    _finish(db, program, user)
    db.refresh(exercise)
    return ExerciseOut.model_validate(exercise)


@router.delete("/exercises/{exercise_id}", status_code=204)
def delete_exercise(exercise_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    exercise = _get_child(db, Exercise, exercise_id, "حرکت")
    session = db.get(WorkoutSession, exercise.session_id)
    program = _editable_of_type(db, session.program_id, WORKOUT, "حرکت")
    session.exercises.remove(exercise)
    for i, e in enumerate(session.exercises):
        e.sort_order = i
    _finish(db, program, user)
    return Response(status_code=204)


@router.get("/programs/{program_id}/nutrition", response_model=list[MealOut])
def list_meals(program_id: uuid.UUID, db: Session = Depends(get_db)):
    return [MealOut.model_validate(m) for m in load_program(db, program_id).meals]


@router.post("/programs/{program_id}/nutrition", response_model=MealOut, status_code=201)
def create_meal(program_id: uuid.UUID, body: MealCreate, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    program = _editable_of_type(db, program_id, NUTRITION, "وعده غذایی")
    meal = NutritionMeal(**body.model_dump(exclude={"sort_order"}), sort_order=0)
    _insert(program.meals, meal, body.sort_order)
    _finish(db, program, user)
    db.refresh(meal)
    return MealOut.model_validate(meal)


@router.put("/nutrition/{meal_id}", response_model=MealOut)
def update_meal(meal_id: uuid.UUID, body: MealWrite, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    meal = _get_child(db, NutritionMeal, meal_id, "وعده")
    program = _editable_of_type(db, meal.program_id, NUTRITION, "وعده غذایی")
    for k, v in body.model_dump().items():
        setattr(meal, k, v)
    _finish(db, program, user)
    db.refresh(meal)
    return MealOut.model_validate(meal)


@router.delete("/nutrition/{meal_id}", status_code=204)
def delete_meal(meal_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    meal = _get_child(db, NutritionMeal, meal_id, "وعده")
    program = _editable_of_type(db, meal.program_id, NUTRITION, "وعده غذایی")
    program.meals.remove(meal)
    for i, m in enumerate(program.meals):
        m.sort_order = i
    _finish(db, program, user)
    return Response(status_code=204)


@router.get("/programs/{program_id}/supplements", response_model=list[SupplementOut])
def list_supplements(program_id: uuid.UUID, db: Session = Depends(get_db)):
    return [SupplementOut.model_validate(x) for x in load_program(db, program_id).supplements]


@router.post("/programs/{program_id}/supplements", response_model=SupplementOut, status_code=201)
def create_supplement(program_id: uuid.UUID, body: SupplementCreate, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    program = _editable_of_type(db, program_id, SUPPLEMENTS, "مکمل/ویتامین")
    item = Supplement(**body.model_dump(exclude={"sort_order"}), sort_order=0)
    _insert(program.supplements, item, body.sort_order)
    _finish(db, program, user)
    db.refresh(item)
    return SupplementOut.model_validate(item)


@router.put("/supplements/{supplement_id}", response_model=SupplementOut)
def update_supplement(supplement_id: uuid.UUID, body: SupplementWrite, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    item = _get_child(db, Supplement, supplement_id, "قلم")
    program = _editable_of_type(db, item.program_id, SUPPLEMENTS, "مکمل/ویتامین")
    for k, v in body.model_dump().items():
        setattr(item, k, v)
    _finish(db, program, user)
    db.refresh(item)
    return SupplementOut.model_validate(item)


@router.delete("/supplements/{supplement_id}", status_code=204)
def delete_supplement(supplement_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = _get_child(db, Supplement, supplement_id, "قلم")
    program = _editable_of_type(db, item.program_id, SUPPLEMENTS, "مکمل/ویتامین")
    program.supplements.remove(item)
    for i, x in enumerate(program.supplements):
        x.sort_order = i
    _finish(db, program, user)
    return Response(status_code=204)


# ---- PDFs ---------------------------------------------------------------------------


@router.post("/programs/{program_id}/generate-pdf", response_model=PdfOut, status_code=201)
def create_pdf(program_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    program = load_program(db, program_id, for_update=True)  # serializes version numbers
    pdf = generate_pdf(db, program, user.id)
    try:
        db.commit()
    except Exception:
        files.delete(pdf.file_path)
        raise
    db.refresh(pdf)
    return pdf_out(pdf, program.updated_at)


@router.get("/programs/{program_id}/pdfs", response_model=list[PdfOut])
def list_pdfs(program_id: uuid.UUID, db: Session = Depends(get_db)):
    program = load_program(db, program_id)
    pdfs = db.scalars(
        select(GeneratedPdf).where(GeneratedPdf.program_id == program_id).order_by(GeneratedPdf.version.desc())
    ).all()
    return [pdf_out(p, program.updated_at) for p in pdfs]


def _download_name(student: Student, program: Program, version: int) -> str:
    raw = f"{full_name(student)} - {program.title} - نسخه {version}"
    safe = re.sub(r'[\\/:*?"<>|\r\n\t]+', " ", raw).strip()[:150]
    return f"{safe}.pdf"


@router.get("/pdfs/{pdf_id}/download")
def download_pdf(pdf_id: uuid.UUID, inline: bool = False, db: Session = Depends(get_db)):
    pdf = db.get(GeneratedPdf, pdf_id)
    if pdf is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فایل پیدا نشد.")
    try:
        path = files.resolve(pdf.file_path)
    except files.StorageError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فایل پیدا نشد.") from None
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فایل پیدا نشد.")
    program = db.get(Program, pdf.program_id)
    student = db.get(Student, pdf.student_id)
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=_download_name(student, program, pdf.version),
        content_disposition_type="inline" if inline else "attachment",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )
