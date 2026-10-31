"""Admin CLI.

    python -m app.cli create-admin      # one-time bootstrap of the single coach account
    python -m app.cli reset-password    # recover access (revokes all sessions)

Credentials come from ADMIN_USERNAME / INITIAL_ADMIN_PASSWORD if set, otherwise an
interactive prompt (password is never echoed). There is no default password.
"""
import argparse
import getpass
import os
import sys

from sqlalchemy import func, select, update

from app.auth.passwords import hash_password, validate_new_password
from app.auth.sessions import now_utc
from app.database import SessionLocal
from app.models import AuthSession, User
from app.services.activity import log_activity


def _read_password(username: str) -> str:
    env_pw = os.environ.get("INITIAL_ADMIN_PASSWORD")
    if env_pw:
        password = env_pw
    else:
        if not sys.stdin.isatty():
            sys.exit("INITIAL_ADMIN_PASSWORD is not set and no interactive terminal is available.")
        password = getpass.getpass("رمز عبور جدید: ")
        if getpass.getpass("تکرار رمز عبور: ") != password:
            sys.exit("رمزها یکسان نیستند.")
    error = validate_new_password(password, username)
    if error:
        sys.exit(error)
    return password


def _read_username() -> str:
    username = os.environ.get("ADMIN_USERNAME") or (input("نام کاربری: ") if sys.stdin.isatty() else "")
    username = username.strip().lower()
    if not (3 <= len(username) <= 64):
        sys.exit("نام کاربری باید بین ۳ تا ۶۴ کاراکتر باشد (ADMIN_USERNAME).")
    return username


def create_admin() -> None:
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(User)) > 0:
            sys.exit("حساب مدیر قبلاً ساخته شده است. برای بازیابی از reset-password استفاده کنید.")
        username = _read_username()
        user = User(username=username, password_hash=hash_password(_read_password(username)), is_active=True)
        db.add(user)
        db.flush()
        log_activity(db, action="auth.admin_created", entity_type="user", entity_id=user.id, actor_user_id=user.id)
        db.commit()
        print(f"حساب مدیر «{username}» ساخته شد. INITIAL_ADMIN_PASSWORD را از .env حذف کنید.")


def reset_password() -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).order_by(User.created_at).limit(1))
        if user is None:
            sys.exit("هنوز حسابی ساخته نشده است. ابتدا create-admin را اجرا کنید.")
        user.password_hash = hash_password(_read_password(user.username))
        user.is_active = True
        db.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=now_utc())
        )
        log_activity(db, action="auth.password_reset", entity_type="user", entity_id=user.id, actor_user_id=user.id)
        db.commit()
        print(f"رمز عبور «{user.username}» تغییر کرد و همه نشست‌ها باطل شدند.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("create-admin", help="ساخت حساب مدیر (فقط یک‌بار)")
    sub.add_parser("reset-password", help="تعیین رمز جدید برای حساب مدیر")
    args = parser.parse_args(argv)
    {"create-admin": create_admin, "reset-password": reset_password}[args.command]()


if __name__ == "__main__":
    main()
