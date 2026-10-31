import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, CreatedAt, Timestamps, UUIDPk
from app.models.enums import ExecutionType, ProgramStatus, ProgramType, str_enum


class Program(UUIDPk, Timestamps, Base):
    __tablename__ = "programs"

    # RESTRICT: approved programs must never be removed by cascading a student delete
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    program_type: Mapped[ProgramType] = mapped_column(str_enum(ProgramType, "program_type"), nullable=False)
    period_number: Mapped[int | None] = mapped_column(Integer)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[ProgramStatus] = mapped_column(
        str_enum(ProgramStatus, "program_status"),
        nullable=False,
        default=ProgramStatus.draft,
        server_default=ProgramStatus.draft.value,
    )
    notes: Mapped[str | None] = mapped_column(Text)
    source_voice_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("voice_records.id", ondelete="SET NULL", use_alter=True)
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sessions: Mapped[list["WorkoutSession"]] = relationship(
        back_populates="program", cascade="all, delete-orphan", order_by="WorkoutSession.sort_order"
    )
    meals: Mapped[list["NutritionMeal"]] = relationship(
        back_populates="program", cascade="all, delete-orphan", order_by="NutritionMeal.sort_order"
    )
    supplements: Mapped[list["Supplement"]] = relationship(
        back_populates="program", cascade="all, delete-orphan", order_by="Supplement.sort_order"
    )

    __table_args__ = (
        Index("ix_programs_student_created", "student_id", "created_at"),
        Index("ix_programs_status", "status"),
    )


class WorkoutSession(UUIDPk, CreatedAt, Base):
    __tablename__ = "workout_sessions"

    program_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text)

    program: Mapped[Program] = relationship(back_populates="sessions")
    exercises: Mapped[list["Exercise"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="Exercise.sort_order"
    )


class Exercise(UUIDPk, Base):
    __tablename__ = "exercises"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workout_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    execution_type: Mapped[ExecutionType] = mapped_column(
        str_enum(ExecutionType, "execution_type"),
        nullable=False,
        default=ExecutionType.reps,
        server_default=ExecutionType.reps.value,
    )
    # All numeric fields nullable: unspecified values must stay NULL (no guessing)
    sets: Mapped[int | None] = mapped_column(Integer)
    reps: Mapped[str | None] = mapped_column(String(64))  # text allows "12-10-8", "تا ناتوانی"
    weight_value: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    weight_unit: Mapped[str | None] = mapped_column(String(16))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    distance_value: Mapped[Decimal | None] = mapped_column(Numeric(9, 2))
    distance_unit: Mapped[str | None] = mapped_column(String(16))
    rest_seconds: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    raw_text: Mapped[str | None] = mapped_column(Text)

    session: Mapped[WorkoutSession] = relationship(back_populates="exercises")


class NutritionMeal(UUIDPk, Base):
    __tablename__ = "nutrition_meals"

    program_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    time_text: Mapped[str | None] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    program: Mapped[Program] = relationship(back_populates="meals")


class Supplement(UUIDPk, Base):
    __tablename__ = "supplements"

    program_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    amount_text: Mapped[str | None] = mapped_column(String(100))
    timing_text: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    program: Mapped[Program] = relationship(back_populates="supplements")
