"""Small, dependency-free primitives for durable local state."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .errors import ContractError


def canonical_json(payload: Any) -> bytes:
    """Return a stable UTF-8 JSON representation with a trailing newline."""

    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def content_hash(payload: Any, length: int = 24) -> str:
    """Hash a JSON-compatible value using its canonical representation."""

    return hashlib.sha256(canonical_json(payload)).hexdigest()[:length]


def read_json(path: Path, default: Any = None) -> Any:
    """Read JSON, returning *default* only when the file does not exist."""

    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return default


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Replace *path* atomically and fsync both file and parent directory."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        try:
            directory_descriptor = os.open(path.parent, os.O_RDONLY)
        except (AttributeError, OSError):
            return
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_write_json(path: Path, payload: Any) -> None:
    """Atomically persist JSON in canonical form."""

    atomic_write_bytes(path, canonical_json(payload))


def atomic_write_text(path: Path, text: str) -> None:
    """Atomically persist UTF-8 text."""

    atomic_write_bytes(path, text.encode("utf-8"))


@contextlib.contextmanager
def exclusive_lock(
    path: Path,
    *,
    timeout_seconds: float = 10.0,
    stale_after_seconds: float = 300.0,
) -> Iterator[None]:
    """Acquire a portable lockfile and remove it on exit.

    The lock uses exclusive file creation rather than a platform-specific file
    locking API. An abandoned lock can be reclaimed after the conservative
    ``stale_after_seconds`` interval.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    descriptor: int | None = None
    while descriptor is None:
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            try:
                stale = time.time() - path.stat().st_mtime > stale_after_seconds
            except FileNotFoundError:
                continue
            if stale:
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
                continue
            if time.monotonic() >= deadline:
                raise ContractError(f"state lock is busy: {path}") from exc
            time.sleep(0.05)
    try:
        os.write(descriptor, f"pid={os.getpid()}\n".encode("ascii"))
        os.fsync(descriptor)
        yield
    finally:
        os.close(descriptor)
        path.unlink(missing_ok=True)


def safe_name(value: str, fallback: str = "item") -> str:
    """Convert an identifier into a conservative filename component."""

    cleaned = "".join(char if char.isalnum() or char in "-_." else "-" for char in value)
    cleaned = cleaned.strip(".-")
    return cleaned[:120] or fallback
