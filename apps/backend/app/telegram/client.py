"""Minimal Telegram Bot API client (sync, httpx).

Only the handful of methods the coach bot needs. Webhook mode: updates arrive
at POST /api/telegram/webhook; this client is used to reply.
"""
import json
import logging
from typing import Any, Protocol

import httpx

from app.config import get_settings

log = logging.getLogger("app.telegram")

MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024  # Bot API getFile limit


class TelegramError(RuntimeError):
    pass


class Bot(Protocol):
    def send_message(self, chat_id: int, text: str, reply_markup: dict | None = None) -> dict: ...
    def answer_callback(self, callback_id: str, text: str | None = None) -> None: ...
    def send_document(self, chat_id: int, filename: str, data: bytes, caption: str | None = None) -> dict: ...
    def download_file(self, file_id: str, max_bytes: int = MAX_DOWNLOAD_BYTES) -> bytes: ...


class TelegramClient:
    def __init__(self, token: str, base: str | None = None, timeout: float = 20.0):
        if not token:
            raise TelegramError("TELEGRAM_BOT_TOKEN is not configured")
        self._token = token
        self._base = (base or get_settings().telegram_api_base).rstrip("/")
        self._http = httpx.Client(timeout=timeout)

    def _call(self, method: str, data: dict | None = None, files: dict | None = None) -> Any:
        url = f"{self._base}/bot{self._token}/{method}"
        try:
            r = self._http.post(url, data=data, files=files) if files else self._http.post(url, json=data or {})
            body = r.json()
        except (httpx.HTTPError, ValueError) as e:
            # Never log the URL: it contains the bot token
            raise TelegramError(f"{method} failed: {type(e).__name__}") from None
        if not body.get("ok"):
            raise TelegramError(f"{method} failed: {body.get('description', 'unknown error')}")
        return body["result"]

    def send_message(self, chat_id: int, text: str, reply_markup: dict | None = None) -> dict:
        data: dict[str, Any] = {"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                                "disable_web_page_preview": True}
        if reply_markup:
            data["reply_markup"] = reply_markup
        return self._call("sendMessage", data)

    def answer_callback(self, callback_id: str, text: str | None = None) -> None:
        data = {"callback_query_id": callback_id}
        if text:
            data["text"] = text
        try:
            self._call("answerCallbackQuery", data)
        except TelegramError as e:  # expired callbacks are harmless
            log.info("answerCallbackQuery: %s", e)

    def send_document(self, chat_id: int, filename: str, data: bytes, caption: str | None = None) -> dict:
        form = {"chat_id": str(chat_id)}
        if caption:
            form["caption"] = caption
        return self._call("sendDocument", form, files={"document": (filename, data, "application/pdf")})

    def download_file(self, file_id: str, max_bytes: int = MAX_DOWNLOAD_BYTES) -> bytes:
        info = self._call("getFile", {"file_id": file_id})
        if info.get("file_size") and info["file_size"] > max_bytes:
            raise TelegramError("file too large")
        url = f"{self._base}/file/bot{self._token}/{info['file_path']}"
        chunks, size = [], 0
        try:
            with self._http.stream("GET", url) as r:
                r.raise_for_status()
                for chunk in r.iter_bytes():
                    size += len(chunk)
                    if size > max_bytes:
                        raise TelegramError("file too large")
                    chunks.append(chunk)
        except httpx.HTTPError as e:
            raise TelegramError(f"download failed: {type(e).__name__}") from None
        return b"".join(chunks)

    def set_webhook(self, url: str, secret: str) -> Any:
        return self._call("setWebhook", {
            "url": url, "secret_token": secret, "allowed_updates": ["message", "callback_query"],
            "drop_pending_updates": True, "max_connections": 5,
        })

    def delete_webhook(self) -> Any:
        return self._call("deleteWebhook", {"drop_pending_updates": False})

    def get_webhook_info(self) -> Any:
        return self._call("getWebhookInfo")


_bot: Bot | None = None


def get_bot() -> Bot:
    global _bot
    if _bot is None:
        _bot = TelegramClient(get_settings().telegram_bot_token)
    return _bot


def set_bot(bot: Bot | None) -> None:
    """Tests inject a fake bot here."""
    global _bot
    _bot = bot


def keyboard(rows: list[list[tuple[str, str]]]) -> dict:
    """Inline keyboard from [(label, callback_data | 'url:https://...')] rows."""
    def button(label: str, action: str) -> dict:
        if action.startswith("url:"):
            return {"text": label, "url": action[4:]}
        return {"text": label, "callback_data": action}

    return {"inline_keyboard": [[button(lbl, act) for lbl, act in row] for row in rows]}


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)
