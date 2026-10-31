"""Background worker: voice -> text -> structure.

    python -m app.worker

Runs separately from the API (same image, different command). Jobs are taken
from the database, so restarts and crashes never lose work.
"""
import logging
import signal
import time

from app.config import get_settings
from app.database import SessionLocal
from app.services.voice_jobs import claim_next, process, purge_retained_audio
from app.telegram.client import get_bot
from app.transcription.whisper import WhisperTranscriber, set_transcriber

log = logging.getLogger("app.worker")
_running = True


def _stop(*_):
    global _running
    _running = False


def run_once(bot, transcriber) -> bool:
    """Process at most one job. Returns True if a job was processed."""
    with SessionLocal() as db:
        voice = claim_next(db)
        if voice is None:
            return False
        log.info("processing voice %s (attempt %s)", voice.id, voice.attempts)
        process(db, voice, bot, transcriber)
        return True


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    s = get_settings()
    transcriber = WhisperTranscriber()
    log.info("loading Whisper model %s (%s/%s)…", s.whisper_model, s.whisper_device, s.whisper_compute_type)
    try:
        # Offline load from the persistent volume: no network call on restart
        transcriber.load(local_files_only=True)
    except Exception:
        log.warning("Whisper model not found in %s — downloading now. Run "
                    "`python -m app.cli download-whisper-model` at install time.", s.whisper_model_dir)
        transcriber.load()
    set_transcriber(transcriber)
    bot = get_bot()
    last_purge = 0.0
    log.info("worker ready")
    while _running:
        try:
            if not run_once(bot, transcriber):
                time.sleep(s.worker_poll_seconds)
            if time.monotonic() - last_purge > 3600:
                with SessionLocal() as db:
                    purge_retained_audio(db)
                last_purge = time.monotonic()
        except Exception:
            log.exception("worker loop error")
            time.sleep(5)
    log.info("worker stopped")


if __name__ == "__main__":
    main()
