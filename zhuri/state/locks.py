"""Cross-process file locking (§5 state/locks).

A minimal advisory lock using ``fcntl`` where available (POSIX), with a portable
fallback to atomic lock-file creation. Used to make concurrent work agents on
different tasks safe (§6.2).
"""
from __future__ import annotations

import contextlib
import os
import time
from pathlib import Path

try:  # pragma: no cover - platform dependent
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX
    fcntl = None  # type: ignore[assignment]


class LockTimeout(TimeoutError):
    """Raised when a lock cannot be acquired within the timeout."""


@contextlib.contextmanager
def file_lock(target: str | os.PathLike, *, timeout: float = 10.0, poll: float = 0.02):
    """Acquire an exclusive lock associated with ``target``.

    The lock is keyed on ``<target>.lock`` so it protects atomic read/modify/
    write cycles on the underlying file across processes.
    """
    lock_path = Path(str(target) + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout

    if fcntl is not None:
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise LockTimeout(f"could not lock {target}")
                    time.sleep(poll)
            yield
        finally:
            with contextlib.suppress(OSError):
                fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        return

    # Portable fallback: exclusive create of a lock file.  # pragma: no cover
    while True:  # pragma: no cover - only on non-POSIX
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise LockTimeout(f"could not lock {target}")
            time.sleep(poll)
    try:  # pragma: no cover
        yield
    finally:  # pragma: no cover
        os.close(fd)
        with contextlib.suppress(FileNotFoundError):
            os.unlink(lock_path)
