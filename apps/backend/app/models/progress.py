import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, CreatedAt, UUIDPk
from app.models.enums import PhotoView, str_enum


class ProgressPhoto(UUIDPk, CreatedAt, Base):
    __tablename__ = "progress_photos"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    capture_date: Mapped[date] = mapped_column(Date, nullable=False)
    view_type: Mapped[PhotoView] = mapped_column(str_enum(PhotoView, "photo_view"), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_progress_photos_student_date", "student_id", "capture_date"),
        # one photo per view per date: makes "compare two dates" unambiguous
        UniqueConstraint("student_id", "capture_date", "view_type", name="uq_progress_photos_student_date_view"),
    )


class BodyMeasurement(UUIDPk, CreatedAt, Base):
    __tablename__ = "body_measurements"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    measured_at: Mapped[date] = mapped_column(Date, nullable=False)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    arm_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    chest_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    waist_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    abdomen_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    thigh_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    hip_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (Index("ix_body_measurements_student_date", "student_id", "measured_at"),)
