import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, CreatedAt, Timestamps, UUIDPk


class GeneratedPdf(UUIDPk, CreatedAt, Base):
    __tablename__ = "generated_pdfs"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    program_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("programs.id", ondelete="RESTRICT"), nullable=False
    )
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    __table_args__ = (UniqueConstraint("program_id", "version", name="uq_generated_pdfs_program_version"),)


class ExerciseDictionaryEntry(UUIDPk, Timestamps, Base):
    __tablename__ = "exercise_dictionary"

    canonical_name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    aliases: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")


class ActivityLog(UUIDPk, CreatedAt, Base):
    __tablename__ = "activity_logs"

    student_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="SET NULL")
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    # "metadata" is reserved on declarative classes; keep the DB column name per spec
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict, server_default="{}")

    __table_args__ = (
        Index("ix_activity_logs_student_created", "student_id", "created_at"),
        Index("ix_activity_logs_created", "created_at"),
    )


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class TelegramConversation(UUIDPk, Base):
    """Bot conversation state persisted in DB so it survives restarts."""

    __tablename__ = "telegram_conversations"

    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    state: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
