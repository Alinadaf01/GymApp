import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.students import get_student_or_404
from app.auth.dependencies import get_current_user
from app.auth.sessions import now_utc
from app.config import get_settings
from app.database import get_db
from app.models import BodyMeasurement, ProgressPhoto, Student, User
from app.models.enums import PhotoView, StudentStatus
from app.schemas.progress import MeasurementIn, MeasurementOut, PhotoOut
from app.services.activity import log_activity
from app.storage import files
from app.storage.images import InvalidImage, sanitize_image

router = APIRouter(tags=["progress"], dependencies=[Depends(get_current_user)])

PHOTO_MAX_SIDE = 1600
THUMB_MAX_SIDE = 480
VIEW_ORDER = {PhotoView.front: 0, PhotoView.back: 1, PhotoView.side: 2}
VIEW_LABELS = {PhotoView.front: "روبه‌رو", PhotoView.back: "پشت", PhotoView.side: "نیم‌رخ"}


# ---- photos -----------------------------------------------------------------------------


def _photo_out(p: ProgressPhoto) -> PhotoOut:
    base = f"/api/photos/{p.id}/file"
    return PhotoOut(id=p.id, capture_date=p.capture_date, view_type=p.view_type, notes=p.notes,
                    created_at=p.created_at, url=base, thumb_url=f"{base}?size=thumb")


@router.post("/students/{student_id}/photos", response_model=PhotoOut, status_code=201)
def upload_photo(
    student_id: uuid.UUID,
    file: UploadFile = File(...),
    view_type: PhotoView = Form(...),
    capture_date: date = Form(...),
    notes: str | None = Form(default=None, max_length=2000),
    consent: bool = Form(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PhotoOut:
    student = get_student_or_404(db, student_id)
    if student.status == StudentStatus.archived:
        raise HTTPException(status.HTTP_409_CONFLICT, "شاگرد بایگانی است.")
    if not (date(2000, 1, 1) <= capture_date <= date.today()):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "تاریخ عکس معتبر نیست.")
    # Spec §11: the student's consent to storing photos is required
    if not consent and student.photo_consent_at is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "برای ثبت تصویر، رضایت شاگرد باید تأیید شود.")
    exists = db.scalar(select(ProgressPhoto.id).where(
        ProgressPhoto.student_id == student.id, ProgressPhoto.capture_date == capture_date,
        ProgressPhoto.view_type == view_type))
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"برای این تاریخ عکس «{VIEW_LABELS[view_type]}» ثبت شده است؛ ابتدا آن را حذف کنید.")

    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    data = file.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE,
                            f"حجم فایل بیش از {get_settings().max_upload_mb} مگابایت است.")
    try:
        clean = sanitize_image(data, file.filename, file.content_type, PHOTO_MAX_SIDE)
        thumb = sanitize_image(clean, "t.jpg", "image/jpeg", THUMB_MAX_SIDE)
    except InvalidImage as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from None

    path = files.write_bytes(files.student_dir(student.id, "progress"), "jpg", clean)
    files.write_beside(path, "thumb", thumb)
    photo = ProgressPhoto(student_id=student.id, capture_date=capture_date, view_type=view_type,
                          file_path=path, notes=(notes or "").strip() or None)
    db.add(photo)
    if student.photo_consent_at is None:
        student.photo_consent_at = now_utc()
    try:
        db.flush()
    except IntegrityError:  # concurrent upload of the same date+view
        db.rollback()
        files.delete(path)
        files.delete(files.companion_path(path, "thumb"))
        raise HTTPException(status.HTTP_409_CONFLICT, "برای این تاریخ و نما عکس ثبت شده است.") from None
    log_activity(db, action="photo.uploaded", entity_type="progress_photo", entity_id=photo.id,
                 student_id=student.id, actor_user_id=user.id,
                 meta={"view": view_type.value, "date": capture_date.isoformat()})
    db.commit()
    db.refresh(photo)
    return _photo_out(photo)


@router.get("/students/{student_id}/photos", response_model=list[PhotoOut])
def list_photos(student_id: uuid.UUID, db: Session = Depends(get_db)) -> list[PhotoOut]:
    get_student_or_404(db, student_id)
    photos = db.scalars(select(ProgressPhoto).where(ProgressPhoto.student_id == student_id)).all()
    photos = sorted(photos, key=lambda p: (-p.capture_date.toordinal(), VIEW_ORDER[p.view_type]))
    return [_photo_out(p) for p in photos]


@router.get("/photos/{photo_id}/file")
def photo_file(photo_id: uuid.UUID, size: str | None = Query(default=None, pattern="^thumb$"),
               db: Session = Depends(get_db)):
    photo = db.get(ProgressPhoto, photo_id)
    if photo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "عکس پیدا نشد.")
    rel = files.companion_path(photo.file_path, "thumb") if size == "thumb" else photo.file_path
    try:
        path = files.resolve(rel)
    except files.StorageError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "عکس پیدا نشد.") from None
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "عکس پیدا نشد.")
    return FileResponse(path, media_type="image/jpeg",
                        headers={"Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff"})


@router.delete("/photos/{photo_id}", status_code=204)
def delete_photo(photo_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    photo = db.get(ProgressPhoto, photo_id)
    if photo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "عکس پیدا نشد.")
    path = photo.file_path
    log_activity(db, action="photo.deleted", entity_type="progress_photo", entity_id=photo.id,
                 student_id=photo.student_id, actor_user_id=user.id,
                 meta={"view": photo.view_type.value, "date": photo.capture_date.isoformat()})
    db.delete(photo)
    db.commit()
    # Deleting the record deletes the files too (spec §11)
    files.delete(path)
    files.delete(files.companion_path(path, "thumb"))
    return Response(status_code=204)


# ---- measurements -----------------------------------------------------------------------


def sync_current_weight(db: Session, student: Student) -> None:
    """Current weight follows the latest measurement that has a weight.
    If no measured weight remains, the manually entered value is left as is."""
    latest = db.scalar(
        select(BodyMeasurement.weight_kg)
        .where(BodyMeasurement.student_id == student.id, BodyMeasurement.weight_kg.is_not(None))
        .order_by(BodyMeasurement.measured_at.desc(), BodyMeasurement.created_at.desc())
        .limit(1)
    )
    if latest is not None:
        student.current_weight_kg = latest


@router.get("/students/{student_id}/measurements", response_model=list[MeasurementOut])
def list_measurements(student_id: uuid.UUID, db: Session = Depends(get_db)):
    get_student_or_404(db, student_id)
    rows = db.scalars(
        select(BodyMeasurement).where(BodyMeasurement.student_id == student_id)
        .order_by(BodyMeasurement.measured_at, BodyMeasurement.created_at)
    ).all()
    return [MeasurementOut.model_validate(m) for m in rows]


@router.post("/students/{student_id}/measurements", response_model=MeasurementOut, status_code=201)
def create_measurement(student_id: uuid.UUID, body: MeasurementIn, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    student = get_student_or_404(db, student_id)
    m = BodyMeasurement(student_id=student.id, **body.model_dump())
    db.add(m)
    db.flush()
    sync_current_weight(db, student)
    log_activity(db, action="measurement.created", entity_type="body_measurement", entity_id=m.id,
                 student_id=student.id, actor_user_id=user.id, meta={"date": body.measured_at.isoformat()})
    db.commit()
    db.refresh(m)
    return MeasurementOut.model_validate(m)


@router.put("/measurements/{measurement_id}", response_model=MeasurementOut)
def update_measurement(measurement_id: uuid.UUID, body: MeasurementIn, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    m = db.get(BodyMeasurement, measurement_id)
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "اندازه‌گیری پیدا نشد.")
    for k, v in body.model_dump().items():
        setattr(m, k, v)
    db.flush()
    sync_current_weight(db, db.get(Student, m.student_id))
    log_activity(db, action="measurement.updated", entity_type="body_measurement", entity_id=m.id,
                 student_id=m.student_id, actor_user_id=user.id, meta={"date": body.measured_at.isoformat()})
    db.commit()
    db.refresh(m)
    return MeasurementOut.model_validate(m)


@router.delete("/measurements/{measurement_id}", status_code=204)
def delete_measurement(measurement_id: uuid.UUID, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    m = db.get(BodyMeasurement, measurement_id)
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "اندازه‌گیری پیدا نشد.")
    student = db.get(Student, m.student_id)
    log_activity(db, action="measurement.deleted", entity_type="body_measurement", entity_id=m.id,
                 student_id=m.student_id, actor_user_id=user.id, meta={"date": m.measured_at.isoformat()})
    db.delete(m)
    db.flush()
    sync_current_weight(db, student)
    db.commit()
    return Response(status_code=204)
