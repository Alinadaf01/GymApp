import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import PhotoView

Cm = Annotated[Decimal, Field(ge=10, le=300, max_digits=4, decimal_places=1)]

MEASURE_FIELDS = ("weight_kg", "arm_cm", "chest_cm", "waist_cm", "abdomen_cm", "thigh_cm", "hip_cm")


class MeasurementIn(BaseModel):
    measured_at: date
    weight_kg: Annotated[Decimal, Field(ge=20, le=400, max_digits=4, decimal_places=1)] | None = None
    arm_cm: Cm | None = None
    chest_cm: Cm | None = None
    waist_cm: Cm | None = None
    abdomen_cm: Cm | None = None
    thigh_cm: Cm | None = None
    hip_cm: Cm | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("measured_at")
    @classmethod
    def _date(cls, v: date) -> date:
        if not (date(2000, 1, 1) <= v <= date.today()):
            raise ValueError("تاریخ اندازه‌گیری معتبر نیست (نمی‌تواند در آینده باشد).")
        return v

    @field_validator("notes")
    @classmethod
    def _notes(cls, v: str | None) -> str | None:
        return (v or "").strip() or None

    @model_validator(mode="after")
    def _at_least_one(self):
        if all(getattr(self, f) is None for f in MEASURE_FIELDS):
            raise ValueError("حداقل یک اندازه را وارد کنید.")
        return self


class MeasurementOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    measured_at: date
    weight_kg: Decimal | None
    arm_cm: Decimal | None
    chest_cm: Decimal | None
    waist_cm: Decimal | None
    abdomen_cm: Decimal | None
    thigh_cm: Decimal | None
    hip_cm: Decimal | None
    notes: str | None
    created_at: datetime


class PhotoOut(BaseModel):
    id: uuid.UUID
    capture_date: date
    view_type: PhotoView
    notes: str | None
    created_at: datetime
    url: str
    thumb_url: str
