import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, CreatedAt, UUIDPk
from app.models.enums import VoiceStatus, str_enum


class VoiceRecord(UUIDPk, CreatedAt, Base):
    """A voice message and its processing job state (persisted so jobs survive restarts)."""

    __tablename__ = "voice_records"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    program_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("programs.id", ondelete="SET NULL")
    )
    telegram_file_id: Mapped[str | None] = mapped_column(String(255))
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    audio_path: Mapped[str | None] = mapped_column(String(512))
    transcript_raw: Mapped[str | None] = mapped_column(Text)
    parsed_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    processing_status: Mapped[VoiceStatus] = mapped_column(
        str_enum(VoiceStatus, "voice_status"),
        nullable=False,
        default=VoiceStatus.received,
        server_default=VoiceStatus.received.value,
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_voice_records_status", "processing_status"),
        Index("ix_voice_records_student", "student_id"),
    )
