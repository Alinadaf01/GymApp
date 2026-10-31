from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, Timestamps, UUIDPk
from app.models.enums import Gender, StudentStatus, str_enum


class Student(UUIDPk, Timestamps, Base):
    __tablename__ = "students"

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32))  # intentionally not unique
    birth_date: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[Gender | None] = mapped_column(str_enum(Gender, "gender"))
    height_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    initial_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    current_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    training_history: Mapped[str | None] = mapped_column(Text)
    goal: Mapped[str | None] = mapped_column(Text)
    limitations_notes: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[date | None] = mapped_column(Date)
    coach_notes: Mapped[str | None] = mapped_column(Text)
    profile_photo_path: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[StudentStatus] = mapped_column(
        str_enum(StudentStatus, "student_status"),
        nullable=False,
        default=StudentStatus.active,
        server_default=StudentStatus.active.value,
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_students_name", "last_name", "first_name"),
        Index("ix_students_phone", "phone"),
        Index("ix_students_status", "status"),
    )
