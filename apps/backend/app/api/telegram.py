import hmac
import logging

from fastapi import APIRouter, Body, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.telegram.bot import handle_update
from app.telegram.client import get_bot

router = APIRouter(prefix="/telegram", tags=["telegram"])
log = logging.getLogger("app.telegram")


@router.post("/webhook")
def webhook(
    update: dict = Body(...),
    secret: str | None = Header(default=None, alias="X-Telegram-Bot-Api-Secret-Token"),
    db: Session = Depends(get_db),
) -> dict:
    """Telegram webhook. Authenticated by the secret token set with setWebhook.
    The coach is then identified by numeric Telegram user id (inside handle_update)."""
    expected = get_settings().telegram_webhook_secret
    if not expected or not secret or not hmac.compare_digest(secret, expected):
        log.warning("telegram webhook: invalid secret")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unauthorized")
    try:
        handle_update(db, update, get_bot())
    except Exception:
        # Always 200: Telegram would otherwise redeliver the same update repeatedly
        log.exception("telegram webhook: update %s failed", update.get("update_id"))
        db.rollback()
    return {"ok": True}
