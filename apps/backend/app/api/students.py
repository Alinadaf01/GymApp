import uuid
from enum import Enum

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import ActivityLog, Program, Student, User
from app.models.enums import StudentStatus
from app.schemas.dashboard import ActivityOut
from app.schemas.student import (
    ProgramSummary,
    StudentCreate,
    StudentListResponse,
    StudentOut,
    StudentUpdate,
)
from app.auth.sessions import now_utc
from app.services.activity import log_activity
from app.services.students import apply_search, full_name, to_list_items, to_out
from app.storage import files
from app.storage.images import InvalidImage, sanitize_image

router = APIRouter(tags=["students"])

NOT_FOUND = "شاگرد پیدا نشد."
PERSIAN_COLLATION = "fa-x-icu"
PROFILE_MAX_SIDE = 1024


class StatusFilter(str, Enum):
    current = "current"  # active + inactive (default; hides archived)
    active = "active"
    inactive = "inactive"
    archived = "archived"
    all = "all"


class SortField(str, Enum):
    name = "name"
    created_at = "created_at"
    start_date = "start_date"
    current_weight = "current_weight"


class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


def get_student_or_404(db: Session, student_id: uuid.UUID) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return student


@router.get("/students", response_model=StudentListResponse)
def list_students(
    q: str | None = Query(default=None, max_length=100),
    status_filter: StatusFilter = Query(default=StatusFilter.current, alias="status"),
    sort: SortField = SortField.created_at,
    order: SortOrder = SortOrder.desc,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> StudentListResponse:
    stmt = select(Student)
    if status_filter == StatusFilter.current:
        stmt = stmt.where(Student.status != StudentStatus.archived)
    elif status_filter != StatusFilter.all:
        stmt = stmt.where(Student.status == StudentStatus(status_filter.value))
    stmt = apply_search(stmt, q)

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))

    columns = {
        # ICU Persian collation: correct order for پ چ ژ گ (needs PostgreSQL built with ICU)
        SortField.name: [Student.last_name.collate(PERSIAN_COLLATION), Student.first_name.collate(PERSIAN_COLLATION)],
        SortField.created_at: [Student.created_at],
        SortField.start_date: [Student.start_date],
        SortField.current_weight: [Student.current_weight_kg],
    }[sort]
    ordering = [(c.asc() if order == SortOrder.asc else c.desc()).nulls_last() for c in columns]
    students = db.scalars(
        stmt.order_by(*ordering, Student.id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return StudentListResponse(items=to_list_items(db, list(students)), total=total, page=page, page_size=page_size)


@router.post("/students", response_model=StudentOut, status_code=status.HTTP_201_CREATED)
def create_student(
    body: StudentCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> StudentOut:
    student = Student(**body.model_dump(), status=StudentStatus.active)
    db.add(student)
    db.flush()
    log_activity(
        db, action="student.created", entity_type="student", entity_id=student.id,
        student_id=student.id, actor_user_id=user.id,
    )
    db.commit()
    db.refresh(student)
    return to_out(db, student)


@router.get("/students/{student_id}", response_model=StudentOut)
def get_student(
    student_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> StudentOut:
    return to_out(db, get_student_or_404(db, student_id))


def _set_status(student: Student, new_status: StudentStatus) -> str | None:
    """Apply a status change; returns the activity action to log, if any."""
    if new_status == student.status:
        return None
    previous = student.status
    student.status = new_status
    if new_status == StudentStatus.archived:
        student.archived_at = now_utc()
        return "student.archived"
    student.archived_at = None
    if previous == StudentStatus.archived:
        return "student.restored"
    return "student.activated" if new_status == StudentStatus.active else "student.deactivated"


@router.put("/students/{student_id}", response_model=StudentOut)
def update_student(
    student_id: uuid.UUID,
    body: StudentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StudentOut:
    student = get_student_or_404(db, student_id)
    data = body.model_dump(exclude={"status"})
    changed = [k for k, v in data.items() if getattr(student, k) != v]
    for k in changed:
        setattr(student, k, data[k])
    if changed:
        # Field names only — values may be sensitive
        log_activity(
            db, action="student.updated", entity_type="student", entity_id=student.id,
            student_id=student.id, actor_user_id=user.id, meta={"fields": changed},
        )
    status_action = _set_status(student, body.status)
    if status_action:
        log_activity(
            db, action=status_action, entity_type="student", entity_id=student.id,
            student_id=student.id, actor_user_id=user.id,
        )
    db.commit()
    db.refresh(student)
    return to_out(db, student)


@router.delete("/students/{student_id}", response_model=StudentOut)
def archive_student(
    student_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> StudentOut:
    """Soft delete: archives the student. Programs, PDFs and history are kept."""
    student = get_student_or_404(db, student_id)
    action = _set_status(student, StudentStatus.archived)
    if action:
        log_activity(
            db, action=action, entity_type="student", entity_id=student.id,
            student_id=student.id, actor_user_id=user.id,
        )
    db.commit()
    db.refresh(student)
    return to_out(db, student)


# ---- profile photo ---------------------------------------------------------


@router.put("/students/{student_id}/profile-photo", response_model=StudentOut)
def upload_profile_photo(
    student_id: uuid.UUID,
    file: UploadFile = File(...),
    consent: bool = Form(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StudentOut:
    student = get_student_or_404(db, student_id)
    if not consent and student.photo_consent_at is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "برای ثبت تصویر، رضایت شاگرد باید تأیید شود."
        )
    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    data = file.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE, f"حجم فایل بیش از {get_settings().max_upload_mb} مگابایت است."
        )
    try:
        clean = sanitize_image(data, file.filename, file.content_type, PROFILE_MAX_SIDE)
    except InvalidImage as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from None

    old_path = student.profile_photo_path
    student.profile_photo_path = files.write_bytes(files.student_dir(student.id, "profile"), "jpg", clean)
    if student.photo_consent_at is None:
        student.photo_consent_at = now_utc()
    log_activity(
        db, action="student.photo_updated", entity_type="student", entity_id=student.id,
        student_id=student.id, actor_user_id=user.id,
    )
    db.commit()
    files.delete(old_path)  # only after the new path is committed
    db.refresh(student)
    return to_out(db, student)


@router.get("/students/{student_id}/profile-photo")
def get_profile_photo(
    student_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    student = get_student_or_404(db, student_id)
    if not student.profile_photo_path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "تصویری ثبت نشده است.")
    try:
        path = files.resolve(student.profile_photo_path)
    except files.StorageError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "تصویری ثبت نشده است.") from None
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "تصویری ثبت نشده است.")
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "private, max-age=86400",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline",
        },
    )


@router.delete("/students/{student_id}/profile-photo", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile_photo(
    student_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    student = get_student_or_404(db, student_id)
    old_path = student.profile_photo_path
    if old_path:
        student.profile_photo_path = None
        log_activity(
            db, action="student.photo_removed", entity_type="student", entity_id=student.id,
            student_id=student.id, actor_user_id=user.id,
        )
        db.commit()
        files.delete(old_path)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- read-only views used by the student profile tabs ----------------------


@router.get("/students/{student_id}/programs", response_model=list[ProgramSummary])
def list_student_programs(
    student_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> list[ProgramSummary]:
    get_student_or_404(db, student_id)
    programs = db.scalars(
        select(Program).where(Program.student_id == student_id).order_by(Program.created_at.desc())
    ).all()
    return [ProgramSummary.model_validate(p, from_attributes=True) for p in programs]


@router.get("/students/{student_id}/activity", response_model=list[ActivityOut])
def student_activity(
    student_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[ActivityOut]:
    student = get_student_or_404(db, student_id)
    logs = db.scalars(
        select(ActivityLog)
        .where(ActivityLog.student_id == student_id)
        .order_by(ActivityLog.created_at.desc())
        .limit(limit)
    ).all()
    return [
        ActivityOut(
            id=a.id, action=a.action, entity_type=a.entity_type, entity_id=a.entity_id,
            student_id=a.student_id, student_name=full_name(student), meta=a.meta, created_at=a.created_at,
        )
        for a in logs
    ]
