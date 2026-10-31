import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from app.models.enums import ProgramStatus, ProgramType, StudentStatus


class StudentBrief(BaseModel):
    id: uuid.UUID
    full_name: str
    phone: str | None
    status: StudentStatus
    current_weight_kg: Decimal | None
    start_date: date | None
    created_at: datetime


class ProgramBrief(BaseModel):
    id: uuid.UUID
    title: str
    program_type: ProgramType
    status: ProgramStatus
    student_id: uuid.UUID
    student_name: str
    approved_at: datetime | None
    created_at: datetime


class DashboardSummary(BaseModel):
    total_students: int
    active_students: int
    total_programs: int
    programs_this_month: int
    recent_students: list[StudentBrief]
    recent_programs: list[ProgramBrief]


class ActivityOut(BaseModel):
    id: uuid.UUID
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    student_id: uuid.UUID | None
    student_name: str | None
    meta: dict[str, Any]
    created_at: datetime
