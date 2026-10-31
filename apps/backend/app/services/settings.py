import re
from typing import Any

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.models import Setting

PDF_TEMPLATE_KEY = "pdf_template"
LOGO_KEY = "pdf_logo_path"


class PdfTemplate(BaseModel):
    club_name: str = Field(default="Basharnia", max_length=100)
    coach_name: str = Field(default="", max_length=100)
    phone: str = Field(default="", max_length=40)
    primary_color: str = Field(default="#1f4e79")
    footer_text: str = Field(default="", max_length=300)

    @field_validator("club_name", "coach_name", "phone", "footer_text")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @field_validator("primary_color")
    @classmethod
    def _color(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.fullmatch(r"#[0-9a-f]{6}", v):
            raise ValueError("رنگ باید به شکل ‎#1f4e79‎ باشد.")
        return v


def _get(db: Session, key: str) -> Any:
    row = db.get(Setting, key)
    return row.value if row else None


def _put(db: Session, key: str, value: Any) -> None:
    row = db.get(Setting, key)
    if row is None:
        db.add(Setting(key=key, value=value))
    else:
        row.value = value


def get_pdf_template(db: Session) -> PdfTemplate:
    stored = _get(db, PDF_TEMPLATE_KEY) or {}
    return PdfTemplate(**{**PdfTemplate().model_dump(), **stored})


def set_pdf_template(db: Session, template: PdfTemplate) -> None:
    _put(db, PDF_TEMPLATE_KEY, template.model_dump())


def get_logo_path(db: Session) -> str | None:
    return _get(db, LOGO_KEY)


def set_logo_path(db: Session, path: str | None) -> None:
    _put(db, LOGO_KEY, path)
