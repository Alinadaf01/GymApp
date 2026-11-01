"""Private file storage on the VPS (outside any public web root).

Paths stored in the DB are *relative* to STORAGE_ROOT. Files are only served through
authenticated API endpoints; there are no public URLs.
"""
import os
import secrets
import tempfile
from pathlib import Path

from app.config import get_settings


class StorageError(Exception):
    pass


def storage_root() -> Path:
    root = get_settings().storage_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve(relative_path: str) -> Path:
    """Resolve a stored relative path and refuse anything escaping STORAGE_ROOT."""
    root = storage_root()
    full = (root / relative_path).resolve()
    if not full.is_relative_to(root):
        raise StorageError("invalid storage path")
    return full


def random_name(extension: str) -> str:
    """Unguessable file name (256-bit random)."""
    return f"{secrets.token_urlsafe(32)}.{extension.lstrip('.')}"


def write_bytes(relative_dir: str, extension: str, data: bytes) -> str:
    """Atomically write data under STORAGE_ROOT/relative_dir; returns the relative path."""
    target_dir = resolve(relative_dir)
    target_dir.mkdir(parents=True, exist_ok=True, mode=0o750)
    name = random_name(extension)
    fd, tmp = tempfile.mkstemp(dir=target_dir, prefix=".upload-")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.chmod(tmp, 0o640)
        os.replace(tmp, target_dir / name)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return f"{relative_dir.rstrip('/')}/{name}"


def write_beside(relative_path: str, suffix: str, data: bytes) -> str:
    """Write a companion file next to an existing one (e.g. a thumbnail)."""
    target = companion_path(relative_path, suffix)
    full = resolve(target)
    tmp = full.with_name(f".{full.name}.tmp")
    tmp.write_bytes(data)
    os.chmod(tmp, 0o640)
    os.replace(tmp, full)
    return target


def companion_path(relative_path: str, suffix: str) -> str:
    stem, dot, ext = relative_path.rpartition(".")
    return f"{stem}.{suffix}.{ext}" if dot else f"{relative_path}.{suffix}"


def delete(relative_path: str | None) -> None:
    if not relative_path:
        return
    try:
        resolve(relative_path).unlink(missing_ok=True)
    except StorageError:
        pass


def student_dir(student_id, kind: str) -> str:
    return f"uploads/students/{student_id}/{kind}"
