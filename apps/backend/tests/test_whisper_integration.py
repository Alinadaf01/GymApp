"""Real local speech-to-text (faster-whisper + FFmpeg), no network.

Skipped unless the model is present in WHISPER_TEST_MODEL_DIR (it is ~460 MB).
Uses synthetic speech from espeak-ng — far worse than a real voice; the goal
is to prove the pipeline works end to end, not to measure accuracy (that needs
the coach's real recordings, spec §8.4).
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

MODEL_DIR = os.environ.get("WHISPER_TEST_MODEL_DIR")
pytestmark = pytest.mark.skipif(
    not MODEL_DIR or not shutil.which("espeak-ng"), reason="Whisper model / espeak-ng not available"
)


def test_whisper_transcribes_persian_speech(tmp_path, monkeypatch):
    from app.config import get_settings
    from app.transcription.audio import probe_duration, to_wav
    from app.transcription.whisper import WhisperTranscriber

    monkeypatch.setattr(get_settings(), "whisper_model_dir", Path(MODEL_DIR))
    src = tmp_path / "speech.wav"
    subprocess.run(["espeak-ng", "-v", "fa", "-s", "140", "-w", str(src),
                    "پرس بالا سینه دمبل چهار ست پانزده تایی"], check=True)
    ogg = tmp_path / "speech.ogg"  # Telegram voices are OGG/Opus
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-c:a", "libopus", str(ogg)], check=True)
    assert 1 < probe_duration(ogg) < 10

    wav = to_wav(ogg, tmp_path / "out.wav")
    text = WhisperTranscriber().transcribe(wav)
    assert text, "empty transcript"
    # Synthetic voice + Opus is hard to recognise: only check real Persian output
    assert "سینه" in text, text
