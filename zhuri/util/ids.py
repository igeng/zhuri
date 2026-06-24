"""Stable, injectable id and timestamp helpers (§0.1 determinism).

Any nondeterminism (ids, timestamps) is funneled through here so tests can seed
or freeze it.
"""
from __future__ import annotations

import datetime as _dt
import os
import random
import re
import threading

_lock = threading.Lock()
_counter = 0
_rng = random.Random()
_frozen_now: _dt.datetime | None = None


def seed(value: int) -> None:
    """Seed the id RNG and reset the monotonic counter (test determinism)."""
    global _counter
    with _lock:
        _rng.seed(value)
        _counter = 0


def freeze_time(when: _dt.datetime | None) -> None:
    """Freeze :func:`now`/:func:`now_iso`. Pass ``None`` to unfreeze."""
    global _frozen_now
    _frozen_now = when


def now() -> _dt.datetime:
    """Current UTC time, honoring :func:`freeze_time`."""
    if _frozen_now is not None:
        return _frozen_now
    return _dt.datetime.now(_dt.timezone.utc)


def now_iso() -> str:
    """ISO-8601 UTC timestamp string."""
    return now().isoformat()


def new_id(prefix: str = "") -> str:
    """Return a short unique id, deterministic when :func:`seed` is used."""
    global _counter
    with _lock:
        _counter += 1
        token = _rng.getrandbits(32)
        count = _counter
    body = f"{count:04d}{token:08x}"
    return f"{prefix}-{body}" if prefix else body


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str, max_len: int = 40) -> str:
    """Lowercase ascii slug suitable for a task directory name."""
    slug = _SLUG_RE.sub("-", text.strip().lower()).strip("-")
    if len(slug) > max_len:
        slug = slug[:max_len].rstrip("-")
    return slug or "task"


def auto_task_id(prompt: str) -> str:
    """Derive an auto task id from a prompt (slug + short unique suffix)."""
    return f"{slugify(prompt, 24)}-{new_id()[:8]}"


def pid() -> int:
    """Current process id (wrapper for testability)."""
    return os.getpid()
