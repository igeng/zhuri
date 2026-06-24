"""Shared pytest fixtures and a deterministic fake provider."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from zhuri.util import ids  # noqa: E402


@pytest.fixture(autouse=True)
def _deterministic():
    """Seed ids deterministically and unfreeze time for every test."""
    ids.seed(1234)
    ids.freeze_time(None)
    yield
    ids.freeze_time(None)


@pytest.fixture
def task_dir(tmp_path):
    d = tmp_path / "task-001"
    (d / "state").mkdir(parents=True)
    (d / "logs").mkdir(parents=True)
    return d
