import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import ExecutionType, ProgramStatus, ProgramType
from app.services.text import normalize_letters, to_ascii_digits

Short = Annotated[str, Field(max_length=200)]
Notes = Annotated[str, Field(max_length=5000)]


def _opt(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    return v or None


def _required_name(v: str) -> str:
    v = normalize_letters(v)
    if not v:
        raise ValueError("این فیلد الزامی است.")
    return v


class _Base(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


# ---- content items (write) ---------------------------------------------------


class ExerciseWrite(_Base):
    """Every numeric field is optional: unspecified values stay null (no guessing)."""

    name: str = Field(min_length=1, max_length=200)
    execution_type: ExecutionType = ExecutionType.reps
    sets: int | None = Field(default=None, ge=1, le=100)
    reps: str | None = Field(default=None, max_length=64)
    weight_value: Decimal | None = Field(default=None, ge=0, le=1000, max_digits=7, decimal_places=2)
    weight_unit: str | None = Field(default=None, max_length=16)
    duration_seconds: int | None = Field(default=None, ge=1, le=86400)
    distance_value: Decimal | None = Field(default=None, ge=0, le=100000, max_digits=9, decimal_places=2)
    distance_unit: str | None = Field(default=None, max_length=16)
    rest_seconds: int | None = Field(default=None, ge=0, le=3600)
    notes: str | None = Field(default=None, max_length=2000)
    raw_text: str | None = Field(default=None, max_length=2000)

    _name = field_validator("name")(classmethod(lambda cls, v: _required_name(v)))
    _opts = field_validator("reps", "weight_unit", "distance_unit", "notes", "raw_text")(
        classmethod(lambda cls, v: _opt(v))
    )

    @field_validator("reps")
    @classmethod
    def _reps_digits(cls, v: str | None) -> str | None:
        # Structured value: store ASCII digits; UI/PDF display Persian digits
        return to_ascii_digits(normalize_letters(v)) if v else v


class SessionWrite(_Base):
    title: str = Field(min_length=1, max_length=200)
    notes: Notes | None = None
    exercises: list[ExerciseWrite] = Field(default_factory=list, max_length=60)

    _title = field_validator("title")(classmethod(lambda cls, v: _required_name(v)))
    _notes = field_validator("notes")(classmethod(lambda cls, v: _opt(v)))


class MealWrite(_Base):
    title: str = Field(min_length=1, max_length=200)
    time_text: str | None = Field(default=None, max_length=32)
    content: str = Field(min_length=1, max_length=5000)
    notes: Notes | None = None

    _title = field_validator("title")(classmethod(lambda cls, v: _required_name(v)))
    _opts = field_validator("time_text", "notes")(classmethod(lambda cls, v: _opt(v)))

    @field_validator("content")
    @classmethod
    def _content(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("محتوای وعده الزامی است.")
        return v.strip()


class SupplementWrite(_Base):
    name: str = Field(min_length=1, max_length=200)
    amount_text: str | None = Field(default=None, max_length=100)
    timing_text: str | None = Field(default=None, max_length=100)
    notes: Notes | None = None

    _name = field_validator("name")(classmethod(lambda cls, v: _required_name(v)))
    _opts = field_validator("amount_text", "timing_text", "notes")(classmethod(lambda cls, v: _opt(v)))


# Granular endpoints (spec §14) — optional explicit position
class SessionCreate(SessionWrite):
    sort_order: int | None = Field(default=None, ge=0)


class SessionUpdate(_Base):
    title: str = Field(min_length=1, max_length=200)
    notes: Notes | None = None
    sort_order: int | None = Field(default=None, ge=0)

    _title = field_validator("title")(classmethod(lambda cls, v: _required_name(v)))
    _notes = field_validator("notes")(classmethod(lambda cls, v: _opt(v)))


class ExerciseCreate(ExerciseWrite):
    sort_order: int | None = Field(default=None, ge=0)


class MealCreate(MealWrite):
    sort_order: int | None = Field(default=None, ge=0)


class SupplementCreate(SupplementWrite):
    sort_order: int | None = Field(default=None, ge=0)


# ---- program (write) ---------------------------------------------------------


class ProgramFields(_Base):
    title: str = Field(min_length=1, max_length=200)
    period_number: int | None = Field(default=None, ge=1, le=999)
    start_date: date | None = None
    end_date: date | None = None
    notes: Notes | None = None

    _title = field_validator("title")(classmethod(lambda cls, v: _required_name(v)))
    _notes = field_validator("notes")(classmethod(lambda cls, v: _opt(v)))

    @model_validator(mode="after")
    def _dates(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("تاریخ پایان نمی‌تواند قبل از تاریخ شروع باشد.")
        return self


class ProgramContent(_Base):
    sessions: list[SessionWrite] = Field(default_factory=list, max_length=20)
    meals: list[MealWrite] = Field(default_factory=list, max_length=30)
    supplements: list[SupplementWrite] = Field(default_factory=list, max_length=50)


class ProgramCreate(ProgramFields, ProgramContent):
    program_type: ProgramType


class ProgramUpdate(ProgramFields, ProgramContent):
    """Full replacement of program fields and content. The type cannot change."""


# ---- output --------------------------------------------------------------------


class ExerciseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    execution_type: ExecutionType
    sets: int | None
    reps: str | None
    weight_value: Decimal | None
    weight_unit: str | None
    duration_seconds: int | None
    distance_value: Decimal | None
    distance_unit: str | None
    rest_seconds: int | None
    notes: str | None
    raw_text: str | None
    sort_order: int


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    notes: str | None
    sort_order: int
    exercises: list[ExerciseOut]


class MealOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    time_text: str | None
    content: str
    notes: str | None
    sort_order: int


class SupplementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    amount_text: str | None
    timing_text: str | None
    notes: str | None
    sort_order: int


class StudentRef(BaseModel):
    id: uuid.UUID
    full_name: str


class PdfOut(BaseModel):
    id: uuid.UUID
    program_id: uuid.UUID
    version: int
    created_at: datetime
    is_outdated: bool  # program changed after this PDF was generated


class ProgramOut(BaseModel):
    id: uuid.UUID
    student: StudentRef
    title: str
    program_type: ProgramType
    period_number: int | None
    start_date: date | None
    end_date: date | None
    status: ProgramStatus
    notes: str | None
    source_voice_record_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None
    sessions: list[SessionOut]
    meals: list[MealOut]
    supplements: list[SupplementOut]
    latest_pdf: PdfOut | None


class ProgramListItem(BaseModel):
    id: uuid.UUID
    student: StudentRef
    title: str
    program_type: ProgramType
    period_number: int | None
    status: ProgramStatus
    start_date: date | None
    end_date: date | None
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None
    pdf_count: int


class ProgramListResponse(BaseModel):
    items: list[ProgramListItem]
    total: int
    page: int
    page_size: int


class NextPeriodOut(BaseModel):
    period_number: int
