import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.sessions import now_utc
from app.models import GeneratedPdf, Program, Student
from app.models.enums import ProgramStatus
from app.pdf.render import PdfRenderError, html_to_pdf, render_html
from app.services.activity import log_activity
from app.services.settings import get_logo_path, get_pdf_template
from app.services.students import full_name
from app.storage import files


def read_logo(db: Session) -> bytes | None:
    path = get_logo_path(db)
    if not path:
        return None
    try:
        full = files.resolve(path)
        return full.read_bytes() if full.is_file() else None
    except files.StorageError:
        return None


def generate_pdf(db: Session, program: Program, user_id: uuid.UUID | None) -> GeneratedPdf:
    """Render and store a new PDF version. Earlier versions are never touched.

    The caller must hold a row lock on the program (SELECT ... FOR UPDATE) so two
    concurrent requests cannot produce the same version number.
    """
    if program.status == ProgramStatus.draft:
        raise HTTPException(status.HTTP_409_CONFLICT, "برای پیش‌نویس PDF ساخته نمی‌شود. ابتدا برنامه را تأیید کنید.")

    student = db.get(Student, program.student_id)
    template = get_pdf_template(db)
    html = render_html(program, full_name(student), template, read_logo(db), issued=now_utc())
    try:
        data = html_to_pdf(html, template)
    except PdfRenderError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "ساخت PDF ناموفق بود. دوباره تلاش کنید.") from None

    version = (
        db.scalar(select(func.max(GeneratedPdf.version)).where(GeneratedPdf.program_id == program.id)) or 0
    ) + 1
    rel_dir = f"pdf/{program.student_id}/{program.id}"
    path = files.write_bytes(rel_dir, "pdf", data)
    pdf = GeneratedPdf(
        student_id=program.student_id,
        program_id=program.id,
        file_path=path,
        version=version,
        created_by_user_id=user_id,
    )
    db.add(pdf)
    try:
        db.flush()
    except Exception:
        files.delete(path)
        raise
    log_activity(
        db, action="pdf.generated", entity_type="pdf", entity_id=pdf.id, student_id=program.student_id,
        actor_user_id=user_id, meta={"program_id": str(program.id), "version": version},
    )
    return pdf
