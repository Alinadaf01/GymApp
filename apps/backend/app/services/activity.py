import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import ActivityLog


def log_activity(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    student_id: uuid.UUID | None = None,
    meta: dict[str, Any] | None = None,
) -> ActivityLog:
    entry = ActivityLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=actor_user_id,
        student_id=student_id,
        meta=meta or {},
    )
    db.add(entry)
    return entry
