from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import User
from app.services.activity import log_activity
from app.services.settings import PdfTemplate, get_logo_path, get_pdf_template, set_logo_path, set_pdf_template
from app.storage import files
from app.storage.images import InvalidImage, sanitize_image

router = APIRouter(prefix="/settings", tags=["settings"], dependencies=[Depends(get_current_user)])


class PdfTemplateOut(PdfTemplate):
    has_logo: bool


def _out(db: Session) -> PdfTemplateOut:
    return PdfTemplateOut(**get_pdf_template(db).model_dump(), has_logo=bool(get_logo_path(db)))


@router.get("/pdf-template", response_model=PdfTemplateOut)
def read_template(db: Session = Depends(get_db)):
    return _out(db)


@router.put("/pdf-template", response_model=PdfTemplateOut)
def update_template(body: PdfTemplate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    set_pdf_template(db, body)
    log_activity(db, action="settings.pdf_template_updated", entity_type="settings", actor_user_id=user.id)
    db.commit()
    return _out(db)


@router.put("/logo", response_model=PdfTemplateOut)
def upload_logo(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    data = file.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "حجم فایل زیاد است.")
    try:
        clean = sanitize_image(data, file.filename, file.content_type, max_side=800)
    except InvalidImage as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from None
    old = get_logo_path(db)
    set_logo_path(db, files.write_bytes("uploads/branding", "jpg", clean))
    log_activity(db, action="settings.logo_updated", entity_type="settings", actor_user_id=user.id)
    db.commit()
    files.delete(old)
    return _out(db)


@router.get("/logo")
def read_logo(db: Session = Depends(get_db)):
    path = get_logo_path(db)
    if not path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "لوگویی ثبت نشده است.")
    full = files.resolve(path)
    if not full.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "لوگویی ثبت نشده است.")
    return FileResponse(full, media_type="image/jpeg", headers={"Cache-Control": "private, no-cache"})


@router.delete("/logo", status_code=204)
def delete_logo(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    old = get_logo_path(db)
    if old:
        set_logo_path(db, None)
        db.commit()
        files.delete(old)
    return Response(status_code=204)
