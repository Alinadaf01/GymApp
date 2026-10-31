"""FFmpeg helpers: probe duration and convert any Telegram audio to 16 kHz mono WAV."""
import json
import subprocess
from pathlib import Path


class AudioError(RuntimeError):
    pass


def probe_duration(path: Path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
            capture_output=True, check=True, timeout=30,
        )
        return float(json.loads(out.stdout)["format"]["duration"])
    except (subprocess.SubprocessError, KeyError, ValueError, json.JSONDecodeError) as e:
        raise AudioError("فایل صوتی قابل خواندن نیست.") from e


def to_wav(src: Path, dst: Path) -> Path:
    try:
        subprocess.run(
            ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
             "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", str(dst)],
            capture_output=True, check=True, timeout=300,
        )
    except subprocess.SubprocessError as e:
        raise AudioError("تبدیل فایل صوتی ناموفق بود.") from e
    return dst
