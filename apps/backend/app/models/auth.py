import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, CreatedAt, UUIDPk


class AuthSession(UUIDPk, CreatedAt, Base):
    """Server-side login session. The cookie holds a random token; only its SHA-256 is stored."""

    __tablename__ = "auth_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(String(255))


class LoginAttempt(UUIDPk, CreatedAt, Base):
    """Failed login attempts, persisted so rate limiting survives restarts and multiple workers."""

    __tablename__ = "login_attempts"

    ip_address: Mapped[str] = mapped_column(String(64), nullable=False)
    username: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        Index("ix_login_attempts_ip_created", "ip_address", "created_at"),
        Index("ix_login_attempts_username_created", "username", "created_at"),
    )
