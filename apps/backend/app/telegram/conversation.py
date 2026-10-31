"""Bot conversation state, persisted in the DB (spec §7.4: survives restarts)."""
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.sessions import now_utc
from app.config import get_settings
from app.models import TelegramConversation

IDLE = "idle"
CHOOSING_STUDENT = "choosing_student"
CHOOSING_TYPE = "choosing_type"
CHOOSING_SESSION = "choosing_session"
AWAITING_VOICE = "awaiting_voice"
PROCESSING = "processing"
REVIEWING = "reviewing"
CORRECTING = "correcting"
SESSION_ADDED = "session_added"


def get_conversation(db: Session, telegram_user_id: int) -> TelegramConversation:
    """Locked conversation row for this user (created on first use; reset when expired)."""
    conv = db.scalar(
        select(TelegramConversation).where(TelegramConversation.telegram_user_id == telegram_user_id).with_for_update()
    )
    if conv is None:
        conv = TelegramConversation(telegram_user_id=telegram_user_id, state=IDLE, payload={})
        db.add(conv)
        db.flush()
    elif conv.expires_at is not None and conv.expires_at < now_utc():
        conv.state, conv.payload = IDLE, {}
    return conv


def set_state(conv: TelegramConversation, state: str, **updates: Any) -> None:
    payload = dict(conv.payload or {})
    payload.update({k: v for k, v in updates.items()})
    conv.state = state
    conv.payload = payload  # new dict so SQLAlchemy sees the JSONB change
    conv.expires_at = now_utc() + timedelta(hours=get_settings().conversation_ttl_hours)


def reset(conv: TelegramConversation) -> None:
    conv.state, conv.payload, conv.expires_at = IDLE, {}, None
