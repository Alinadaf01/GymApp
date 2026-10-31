import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AuthSession, LoginAttempt, User


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def now_utc() -> datetime:
    return datetime.now(UTC)


def create_session(db: Session, user: User, user_agent: str | None) -> tuple[str, AuthSession]:
    token = secrets.token_urlsafe(32)
    session = AuthSession(
        user_id=user.id,
        token_hash=_hash_token(token),
        expires_at=now_utc() + timedelta(hours=get_settings().session_ttl_hours),
        user_agent=(user_agent or "")[:255] or None,
    )
    db.add(session)
    db.flush()
    return token, session


def get_session_user(db: Session, token: str | None) -> tuple[AuthSession, User] | None:
    if not token:
        return None
    row = db.execute(
        select(AuthSession, User)
        .join(User, User.id == AuthSession.user_id)
        .where(
            AuthSession.token_hash == _hash_token(token),
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > func.now(),
            User.is_active.is_(True),
        )
    ).first()
    if row is None:
        return None
    session, user = row
    # Throttle writes: update last_seen at most once per 5 minutes
    if session.last_seen_at is None or now_utc() - session.last_seen_at > timedelta(minutes=5):
        session.last_seen_at = now_utc()
        db.commit()
    return session, user


def revoke_session(db: Session, session: AuthSession) -> None:
    session.revoked_at = now_utc()


def revoke_other_sessions(db: Session, user: User, keep_session_id) -> None:
    db.execute(
        update(AuthSession)
        .where(
            AuthSession.user_id == user.id,
            AuthSession.id != keep_session_id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=now_utc())
    )


# ---- login rate limiting -------------------------------------------------


def is_login_blocked(db: Session, ip: str, username: str) -> bool:
    s = get_settings()
    since = now_utc() - timedelta(minutes=s.login_window_minutes)
    by_user = db.scalar(
        select(func.count()).where(LoginAttempt.username == username, LoginAttempt.created_at > since)
    )
    by_ip = db.scalar(select(func.count()).where(LoginAttempt.ip_address == ip, LoginAttempt.created_at > since))
    return by_user >= s.login_max_failures_per_user or by_ip >= s.login_max_failures_per_ip


def record_failed_login(db: Session, ip: str, username: str) -> None:
    db.add(LoginAttempt(ip_address=ip[:64], username=username[:64]))
    # Housekeeping: drop attempts older than a day
    db.execute(delete(LoginAttempt).where(LoginAttempt.created_at < now_utc() - timedelta(days=1)))


def clear_failed_logins(db: Session, username: str) -> None:
    db.execute(delete(LoginAttempt).where(LoginAttempt.username == username))
