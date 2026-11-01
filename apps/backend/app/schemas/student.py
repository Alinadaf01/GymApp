import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import Gender, ProgramStatus, ProgramType, StudentStatus
from app.services.text import normalize_persian, normalize_phone

Height = Annotated[Decimal, Field(ge=50, le=260, max_digits=4, decimal_places=1)]
Weight = Annotated[Decimal, Field(ge=20, le=400, max_digits=4, decimal_places=1)]
LongText = Annotated[str, Field(max_length=5000)]


def _clean_optional_text(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    return v or None


class StudentFields(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=32)
    birth_date: date | None = None
    gender: Gender | None = None
    height_cm: Height | None = None
    initial_weight_kg: Weight | None = None
    current_weight_kg: Weight | None = None
    training_history: LongText | None = None
    goal: LongText | None = None
    limitations_notes: LongText | None = None
    start_date: date | None = None
    coach_notes: LongText | None = None

    @field_validator("first_name", "last_name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = normalize_persian(v)
        if not v:
            raise ValueError("این فیلد الزامی است.")
        return v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        if v is None or not v.strip():
            return None
        p = normalize_phone(v)
        digits = p.lstrip("+")
        if not (7 <= len(digits) <= 15):
            raise ValueError("شماره موبایل معتبر نیست.")
        return p

    @field_validator("training_history", "goal", "limitations_notes", "coach_notes")
    @classmethod
    def _text(cls, v: str | None) -> str | None:
        return _clean_optional_text(v)

    @field_validator("birth_date")
    @classmethod
    def _birth(cls, v: date | None) -> date | None:
        if v is not None and not (date(1900, 1, 1) <= v <= date.today()):
            raise ValueError("تاریخ تولد معتبر نیست.")
        return v

    @field_validator("start_date")
    @classmethod
    def _start(cls, v: date | None) -> date | None:
        if v is not None and not (date(2000, 1, 1) <= v <= date(2100, 1, 1)):
            raise ValueError("تاریخ شروع معتبر نیست.")
        return v


class StudentCreate(StudentFields):
    pass


class StudentUpdate(StudentFields):
    """Full replacement (PUT). Status may be changed here; archiving also via DELETE."""

    status: StudentStatus = StudentStatus.active


class PhotoConsent(BaseModel):
    consent: Literal[True]


class LastProgram(BaseModel):
    id: uuid.UUID
    title: str
    program_type: ProgramType
    status: ProgramStatus
    date: datetime


class StudentOut(BaseModel):
    """Output only: plain types, no input validation rules."""

    id: uuid.UUID
    first_name: str
    last_name: str
    full_name: str
    phone: str | None
    birth_date: date | None
    gender: Gender | None
    height_cm: Decimal | None
    initial_weight_kg: Decimal | None
    current_weight_kg: Decimal | None
    training_history: str | None
    goal: str | None
    limitations_notes: str | None
    start_date: date | None
    coach_notes: str | None
    status: StudentStatus
    profile_photo_url: str | None
    photo_consent_at: datetime | None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    last_program: LastProgram | None


class StudentListItem(BaseModel):
    id: uuid.UUID
    full_name: str
    first_name: str
    last_name: str
    phone: str | None
    current_weight_kg: Decimal | None
    start_date: date | None
    status: StudentStatus
    profile_photo_url: str | None
    last_program: LastProgram | None
    created_at: datetime


class StudentListResponse(BaseModel):
    items: list[StudentListItem]
    total: int
    page: int
    page_size: int


class ProgramSummary(BaseModel):
    id: uuid.UUID
    title: str
    program_type: ProgramType
    status: ProgramStatus
    period_number: int | None
    start_date: date | None
    end_date: date | None
    created_at: datetime
    approved_at: datetime | None
