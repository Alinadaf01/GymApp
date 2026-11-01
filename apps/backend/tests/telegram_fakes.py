"""Test doubles for Telegram and Whisper (tests only; never used in production)."""
import subprocess
from functools import cache
from pathlib import Path

from app.telegram.client import TelegramError

COACH = 111
SECRET = "test-webhook-secret-0123456789"


@cache
def ogg_bytes() -> bytes:
    out = Path("/tmp/basharnia-test-voice.ogg")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                    "sine=frequency=440:duration=1", "-c:a", "libopus", "-y", str(out)], check=True)
    return out.read_bytes()


class FakeBot:
    def __init__(self):
        self.sent: list[dict] = []
        self.documents: list[dict] = []
        self.answers: list[tuple] = []
        self.download_error: Exception | None = None
        self.downloads = 0

    def send_message(self, chat_id, text, reply_markup=None):
        self.sent.append({"chat_id": chat_id, "text": text, "markup": reply_markup})
        return {"message_id": len(self.sent)}

    def answer_callback(self, callback_id, text=None):
        self.answers.append((callback_id, text))

    def send_document(self, chat_id, filename, data, caption=None):
        assert data.startswith(b"%PDF")
        self.documents.append({"chat_id": chat_id, "filename": filename, "size": len(data), "caption": caption})
        return {}

    def download_file(self, file_id, max_bytes=20 * 1024 * 1024):
        self.downloads += 1
        if self.download_error:
            raise self.download_error
        return ogg_bytes()

    # helpers
    @property
    def last(self) -> dict:
        return self.sent[-1]

    def buttons(self, msg: dict | None = None) -> list[tuple[str, str]]:
        markup = (msg or self.last)["markup"] or {}
        return [(b["text"], b.get("callback_data") or b.get("url")) for row in markup.get("inline_keyboard", [])
                for b in row]

    def callback(self, label_part: str, msg: dict | None = None) -> str:
        for text, data in self.buttons(msg):
            if label_part in text:
                return data
        raise AssertionError(f"button {label_part!r} not in {self.buttons(msg)}")


class FakeTranscriber:
    def __init__(self, text: str = ""):
        self.text = text
        self.calls = 0
        self.prompts: list[str | None] = []
        self.error: Exception | None = None

    def transcribe(self, wav_path, prompt=None):
        assert Path(wav_path).read_bytes()[:4] == b"RIFF"  # FFmpeg produced a real WAV
        self.calls += 1
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        return self.text


_update_id = 0


def _next_id() -> int:
    global _update_id
    _update_id += 1
    return _update_id


def text_update(text: str, user_id: int = COACH, chat_type: str = "private") -> dict:
    return {"update_id": _next_id(), "message": {
        "message_id": _next_id(), "text": text, "from": {"id": user_id, "username": "coach"},
        "chat": {"id": user_id, "type": chat_type}}}


def voice_update(duration: int = 5, user_id: int = COACH, file_id: str = "VOICE1") -> dict:
    return {"update_id": _next_id(), "message": {
        "message_id": _next_id(), "voice": {"file_id": file_id, "duration": duration, "file_size": 5000,
                                            "mime_type": "audio/ogg"},
        "from": {"id": user_id}, "chat": {"id": user_id, "type": "private"}}}


def callback_update(data: str, user_id: int = COACH) -> dict:
    return {"update_id": _next_id(), "callback_query": {
        "id": f"cb{_next_id()}", "data": data, "from": {"id": user_id},
        "message": {"message_id": 1, "chat": {"id": user_id, "type": "private"}}}}


__all__ = ["COACH", "SECRET", "FakeBot", "FakeTranscriber", "TelegramError", "callback_update", "text_update",
           "voice_update"]
