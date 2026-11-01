"""Local speech-to-text with faster-whisper (no paid API, spec §8).

The model is loaded once per process and reused; it lives in a persistent
directory (WHISPER_MODEL_DIR) and is downloaded at install time with
`python -m app.cli download-whisper-model`, not on every restart.
"""
import threading
from pathlib import Path
from typing import Protocol

from app.config import get_settings


class Transcriber(Protocol):
    def transcribe(self, wav_path: Path, prompt: str | None = None) -> str: ...


class WhisperTranscriber:
    def __init__(self) -> None:
        self._model = None
        self._lock = threading.Lock()  # one transcription at a time per process

    def load(self, local_files_only: bool = False):
        if self._model is None:
            from faster_whisper import WhisperModel

            s = get_settings()
            s.whisper_model_dir.mkdir(parents=True, exist_ok=True)
            self._model = WhisperModel(
                s.whisper_model,
                device=s.whisper_device,
                compute_type=s.whisper_compute_type,
                download_root=str(s.whisper_model_dir),
                local_files_only=local_files_only,
            )
        return self._model

    def transcribe(self, wav_path: Path, prompt: str | None = None) -> str:
        with self._lock:
            model = self.load()
            segments, _info = model.transcribe(
                str(wav_path),
                language="fa",
                vad_filter=True,
                beam_size=get_settings().whisper_beam_size,
                # Vocabulary hint (exercise names, units) improves recognition of gym terms
                initial_prompt=prompt,
                condition_on_previous_text=False,
            )
            return " ".join(s.text.strip() for s in segments).strip()


_default: Transcriber | None = None


def get_transcriber() -> Transcriber:
    global _default
    if _default is None:
        _default = WhisperTranscriber()
    return _default


def set_transcriber(t: Transcriber | None) -> None:
    """Tests inject a fake transcriber here."""
    global _default
    _default = t


# A short sample in the coach's own style: Whisper copies the spelling and
# punctuation of its prompt much better than it follows a bare word list.
PROMPT_STYLE = (
    "پرس سینه هالتر، سه ست، دوازده تکرار. جلو بازو دمبل چکشی، چهار ست، چهارده تکرار. "
    "اسکوات، پنج ست، پانزده تایی، استراحت نود ثانیه. پلانک، سه ست، یک دقیقه."
)


def vocabulary_prompt(exercise_names: list[str], limit: int = 20) -> str:
    # Whisper keeps only the LAST ~224 prompt tokens, so the style sample goes last
    # and the name list stays short (Persian takes several tokens per word).
    names = "، ".join(exercise_names[:limit])
    return f"{names}. {PROMPT_STYLE}" if names else PROMPT_STYLE
