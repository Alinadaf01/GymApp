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


def download_whisper_model() -> None:
    """Install step: fetch the Whisper model into WHISPER_MODEL_DIR (persistent volume)."""
    from app.config import get_settings
    from app.transcription.whisper import WhisperTranscriber

    s = get_settings()
    print(f"Downloading Whisper '{s.whisper_model}' into {s.whisper_model_dir} …")
    WhisperTranscriber().load()
    print("Done.")


def _bot():
    from app.config import get_settings
    from app.telegram.client import TelegramClient

    return TelegramClient(get_settings().telegram_bot_token)


def set_webhook() -> None:
    from app.config import get_settings

    s = get_settings()
    if not s.telegram_webhook_secret or len(s.telegram_webhook_secret) < 24:
        sys.exit("TELEGRAM_WEBHOOK_SECRET must be set (at least 24 characters).")
    if s.telegram_allowed_user_id is None:
        sys.exit("TELEGRAM_ALLOWED_USER_ID must be set.")
    url = s.api_base_url.rstrip("/") + "/api/telegram/webhook"
    if not url.startswith("https://"):
        sys.exit("API_BASE_URL must be https:// for a Telegram webhook.")
    _bot().set_webhook(url, s.telegram_webhook_secret)
    print(f"Webhook set: {url}")


def webhook_info() -> None:
    info = _bot().get_webhook_info()
    print({k: v for k, v in info.items() if k in ("url", "pending_update_count", "last_error_message",
                                                   "last_error_date", "max_connections")})


def delete_webhook() -> None:
    _bot().delete_webhook()
    print("Webhook deleted.")


def export_voice_eval(since: str | None = None) -> None:
    """Export voices for accuracy evaluation (spec §8.4) as JSON on stdout:
    Whisper's raw text, the coach's text correction, what the parser produced and
    the program as finally saved (after any edits in the panel). The coach's
    corrections and final values are the ground truth for tuning the parser.

        docker compose run --rm -T api python -m app.cli export-voice-eval > voice-eval.json
    """
    import json
    from datetime import date

    from app.models import Program, Student, VoiceRecord
    from app.services.programs import load_program

    with SessionLocal() as db:
        stmt = select(VoiceRecord).order_by(VoiceRecord.created_at)
        if since:
            stmt = stmt.where(VoiceRecord.created_at >= date.fromisoformat(since))
        items = []
        for v in db.scalars(stmt):
            program_doc = None
            if v.program_id and db.get(Program, v.program_id):
                p = load_program(db, v.program_id)
                program_doc = {
                    "status": p.status.value,
                    "sessions": [
                        {"title": s.title, "notes": s.notes, "exercises": [
                            {k: (str(getattr(e, k)) if getattr(e, k) is not None else None)
                             for k in ("name", "sets", "reps", "weight_value", "weight_unit", "duration_seconds",
                                       "distance_value", "distance_unit", "rest_seconds", "notes", "raw_text")}
                            for e in s.exercises]}
                        for s in p.sessions
                    ],
                    "meals": [{"title": m.title, "time_text": m.time_text, "content": m.content} for m in p.meals],
                    "supplements": [{"name": x.name, "amount_text": x.amount_text, "timing_text": x.timing_text}
                                    for x in p.supplements],
                }
            student = db.get(Student, v.student_id)
            items.append({
                "id": str(v.id),
                "created_at": v.created_at.isoformat(),
                "student": f"{student.first_name} {student.last_name}" if student else None,
                "program_type": v.program_type,
                "session_title": v.session_title,
                "duration_seconds": v.duration_seconds,
                "status": v.processing_status.value,
                "transcript_raw": v.transcript_raw,
                "corrected_text": v.corrected_text,
                "parsed": v.parsed_payload,
                "final_program": program_doc,
                "audio_file": v.audio_path,  # present only while AUDIO_RETAIN_HOURS > 0
            })
        json.dump({"exported_at": date.today().isoformat(), "count": len(items), "voices": items},
                  sys.stdout, ensure_ascii=False, indent=1)
        sys.stdout.write("\n")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("create-admin", help="ساخت حساب مدیر (فقط یک‌بار)")
    sub.add_parser("reset-password", help="تعیین رمز جدید برای حساب مدیر")
    sub.add_parser("download-whisper-model", help="دانلود مدل Whisper در پوشه دائمی")
    sub.add_parser("set-webhook", help="ثبت Webhook تلگرام")
    sub.add_parser("webhook-info", help="وضعیت Webhook تلگرام")
    sub.add_parser("delete-webhook", help="حذف Webhook تلگرام")
    ev = sub.add_parser("export-voice-eval", help="خروجی ویس‌ها برای سنجش دقت (JSON)")
    ev.add_argument("--since", help="فقط ویس‌های از این تاریخ (YYYY-MM-DD)")
    args = parser.parse_args(argv)
    if args.command == "export-voice-eval":
        return export_voice_eval(args.since)
    {
        "create-admin": create_admin,
        "reset-password": reset_password,
        "download-whisper-model": download_whisper_model,
        "set-webhook": set_webhook,
        "webhook-info": webhook_info,
        "delete-webhook": delete_webhook,
    }[args.command]()


if __name__ == "__main__":
    main()
