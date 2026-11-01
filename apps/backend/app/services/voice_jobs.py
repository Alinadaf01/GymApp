"""Voice processing jobs. State lives in voice_records (not in memory), so a
restart never loses work: interrupted jobs are picked up again (spec §19).

received/queued -> downloading -> transcribing -> parsing -> awaiting_review
                                         (errors) -> queued (retry) | failed
"""
import logging
from datetime import timedelta
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth.sessions import now_utc
from app.config import get_settings
from app.models import TelegramConversation, VoiceRecord
from app.models.enums import VoiceStatus
from app.parsers.service import load_dictionary, parse_text
from app.storage import files
from app.telegram import conversation as cv
from app.telegram.bot import send_failure, send_review
from app.telegram.client import Bot, TelegramError
from app.transcription.audio import AudioError, probe_duration, to_wav
from app.transcription.whisper import Transcriber, vocabulary_prompt

log = logging.getLogger("app.voice")

READY = (VoiceStatus.received, VoiceStatus.queued)
IN_PROGRESS = (VoiceStatus.downloading, VoiceStatus.transcribing, VoiceStatus.parsing)


class PermanentError(Exception):
    """Retrying will not help (e.g. audio too long, silence)."""


class Cancelled(Exception):
    """The coach cancelled / re-recorded while the job was running."""


def claim_next(db: Session) -> VoiceRecord | None:
    """Take the oldest ready job (or one stuck in progress after a crash).
    SKIP LOCKED lets several workers run safely."""
    stale = now_utc() - timedelta(minutes=get_settings().voice_stale_minutes)
    voice = db.scalar(
        select(VoiceRecord)
        .where(or_(
            VoiceRecord.processing_status.in_(READY),
            (VoiceRecord.processing_status.in_(IN_PROGRESS)) & (VoiceRecord.processing_started_at < stale),
        ))
        .order_by(VoiceRecord.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if voice is None:
        return None
    voice.processing_status = VoiceStatus.downloading
    voice.processing_started_at = now_utc()
    voice.attempts += 1
    db.commit()
    return voice


def _set_status(db: Session, voice: VoiceRecord, status: VoiceStatus) -> None:
    if not _still_wanted(db, voice):  # never overwrite a cancellation
        raise Cancelled
    voice.processing_status = status
    voice.processing_started_at = now_utc()
    db.commit()


def _still_wanted(db: Session, voice: VoiceRecord) -> bool:
    """Lock the row and read its *current* status (the coach may have cancelled
    meanwhile) without discarding the transcript/parse held in memory."""
    current = db.scalar(
        select(VoiceRecord.processing_status).where(VoiceRecord.id == voice.id).with_for_update()
    )
    return current not in (VoiceStatus.cancelled, VoiceStatus.approved)


def process(db: Session, voice: VoiceRecord, bot: Bot, transcriber: Transcriber) -> None:
    s = get_settings()
    tmp_dir = "audio/temporary"
    wav_path: Path | None = None
    if voice.attempts > s.voice_max_attempts:  # e.g. the job crashed the worker repeatedly
        _fail(db, bot, voice, "پردازش این ویس چند بار ناموفق بود.", retry=True)
        _cleanup_audio(db, voice)
        return
    try:
        # 1) download from Telegram (keep only an unguessable local name)
        if not voice.audio_path or not files.resolve(voice.audio_path).is_file():
            data = bot.download_file(voice.telegram_file_id)
            voice.audio_path = files.write_bytes(tmp_dir, "ogg", data)
        src = files.resolve(voice.audio_path)
        duration = probe_duration(src)
        voice.duration_seconds = int(duration)
        if duration > s.audio_max_duration_seconds:
            raise PermanentError("ویس از حداکثر مدت مجاز طولانی‌تر است.")

        # 2) FFmpeg -> 16 kHz mono WAV, then local Whisper
        _set_status(db, voice, VoiceStatus.transcribing)
        wav_path = src.with_suffix(".wav")
        to_wav(src, wav_path)
        dictionary = load_dictionary(db)
        prompt = vocabulary_prompt(dictionary.canonical_names) if s.whisper_vocab_hint else None
        text = transcriber.transcribe(wav_path, prompt=prompt)
        if not text.strip():
            raise PermanentError("گفتاری در ویس تشخیص داده نشد. دوباره و واضح‌تر ضبط کنید.")
        voice.transcript_raw = text

        # 3) parse (a parser error must not lose the transcript)
        _set_status(db, voice, VoiceStatus.parsing)
        try:
            voice.parsed_payload = parse_text(text, voice.program_type, dictionary, voice.session_title)
        except Exception:
            log.exception("parser failed for voice %s", voice.id)
            voice.parsed_payload = None
        if not _still_wanted(db, voice):  # cancelled by the coach meanwhile
            raise Cancelled
        voice.processing_status = VoiceStatus.awaiting_review
        voice.processed_at = now_utc()
        voice.error_message = None
        _move_conversation_to_review(db, voice)
        db.commit()
        send_review(db, bot, voice)
    except Cancelled:
        db.rollback()
        db.refresh(voice)
        log.info("voice %s cancelled during processing", voice.id)
    except PermanentError as e:
        _fail(db, bot, voice, str(e), retry=False)
    except (TelegramError, AudioError, OSError, RuntimeError) as e:
        log.warning("voice %s attempt %s failed: %s", voice.id, voice.attempts, type(e).__name__)
        db.rollback()
        db.refresh(voice)
        if voice.attempts < s.voice_max_attempts:
            voice.processing_status = VoiceStatus.queued
            voice.error_message = type(e).__name__
            db.commit()
        else:
            message = "دریافت ویس از تلگرام ناموفق بود." if isinstance(e, TelegramError) else "تبدیل ویس به متن ناموفق بود."
            _fail(db, bot, voice, message, retry=True)
    finally:
        if wav_path is not None:
            wav_path.unlink(missing_ok=True)
        _cleanup_audio(db, voice)


def _move_conversation_to_review(db: Session, voice: VoiceRecord) -> None:
    for conv in db.scalars(select(TelegramConversation).with_for_update()):
        if (conv.payload or {}).get("voice_id") == str(voice.id) and conv.state == cv.PROCESSING:
            cv.set_state(conv, cv.REVIEWING)


def _fail(db: Session, bot: Bot, voice: VoiceRecord, message: str, retry: bool) -> None:
    db.rollback()
    db.refresh(voice)
    voice.processing_status = VoiceStatus.failed
    voice.error_message = message
    db.commit()
    try:
        send_failure(bot, voice, message, retry)
    except TelegramError:
        log.warning("could not notify coach about failed voice %s", voice.id)


def _cleanup_audio(db: Session, voice: VoiceRecord) -> None:
    """Raw audio is not retained by default (spec §16)."""
    if get_settings().audio_retain_hours == 0 and voice.audio_path and voice.processing_status in (
        VoiceStatus.awaiting_review, VoiceStatus.failed, VoiceStatus.cancelled,
    ):
        files.delete(voice.audio_path)
        voice.audio_path = None
        voice.deleted_at = now_utc()
        db.commit()


def purge_retained_audio(db: Session) -> int:
    """Delete audio older than AUDIO_RETAIN_HOURS (when retention is enabled)."""
    hours = get_settings().audio_retain_hours
    if hours <= 0:
        return 0
    cutoff = now_utc() - timedelta(hours=hours)
    count = 0
    for voice in db.scalars(select(VoiceRecord).where(VoiceRecord.audio_path.is_not(None),
                                                      VoiceRecord.created_at < cutoff)):
        files.delete(voice.audio_path)
        voice.audio_path = None
        voice.deleted_at = now_utc()
        count += 1
    db.commit()
    return count
