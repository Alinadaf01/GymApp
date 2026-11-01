import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentAuth, get_current_auth
from app.auth.passwords import hash_password, needs_rehash, validate_new_password, verify_password
from app.auth.sessions import (
    clear_failed_logins,
    create_session,
    is_login_blocked,
    record_failed_login,
    revoke_other_sessions,
    revoke_session,
)
from app.config import get_settings
from app.database import get_db
from app.models import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest, UserOut
from app.services.activity import log_activity

router = APIRouter(prefix="/auth", tags=["auth"])
security_log = logging.getLogger("app.security")

INVALID_CREDENTIALS = "نام کاربری یا رمز عبور اشتباه است."
TOO_MANY_ATTEMPTS = "تلاش‌های ناموفق زیاد بود. چند دقیقه دیگر دوباره امتحان کنید."


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _set_session_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(
        key=s.session_cookie_name,
        value=token,
        max_age=s.session_ttl_hours * 3600,
        httponly=True,
        secure=s.cookie_secure,
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(
        key=s.session_cookie_name, path="/", httponly=True, secure=s.cookie_secure, samesite="lax"
    )


@router.post("/login", response_model=UserOut)
def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> UserOut:
    username = body.username.strip().lower()
    ip = _client_ip(request)

    if is_login_blocked(db, ip, username):
        security_log.warning("login blocked by rate limit ip=%s", ip)
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, TOO_MANY_ATTEMPTS)

    user = db.scalar(select(User).where(User.username == username))
    ok = verify_password(user.password_hash if user else None, body.password)
    if not ok or user is None or not user.is_active:
        record_failed_login(db, ip, username)
        db.commit()
        security_log.warning("failed login ip=%s", ip)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_CREDENTIALS)

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    clear_failed_logins(db, username)
    token, _ = create_session(db, user, request.headers.get("user-agent"))
    db.commit()
    _set_session_cookie(response, token)
    return UserOut(id=user.id, username=user.username)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, auth: CurrentAuth = Depends(get_current_auth), db: Session = Depends(get_db)):
    revoke_session(db, db.merge(auth.session))
    db.commit()
    _clear_session_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserOut)
def me(auth: CurrentAuth = Depends(get_current_auth)) -> UserOut:
    return UserOut(id=auth.user.id, username=auth.user.username)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    body: ChangePasswordRequest,
    response: Response,
    auth: CurrentAuth = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    user = db.merge(auth.user)
    if not verify_password(user.password_hash, body.current_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "رمز عبور فعلی اشتباه است.")
    error = validate_new_password(body.new_password, user.username)
    if error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, error)
    if verify_password(user.password_hash, body.new_password):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "رمز جدید باید با رمز فعلی متفاوت باشد.")

    user.password_hash = hash_password(body.new_password)
    # Sign out every other device; keep the current session
    revoke_other_sessions(db, user, auth.session.id)
    log_activity(db, action="auth.password_changed", entity_type="user", entity_id=user.id, actor_user_id=user.id)
    db.commit()
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
