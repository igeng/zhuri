"""Atomic, locked read/write of state files (§6.2, §6.4).

All writes go through a temp-file + ``os.replace`` (atomic on POSIX) under a
cross-process :func:`file_lock`, so concurrent work agents on different tasks
never corrupt state. Append-only files (`findings.jsonl`, `iteration_log.jsonl`)
are appended under the same lock.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from ..util import ids
from .locks import file_lock
from .models import Direction, Finding, IterationLog, Progress

STATE_FILES = {
    "task_spec": "task_spec.md",
    "progress": "progress.json",
    "findings": "findings.jsonl",
    "directions": "directions_tried.json",
    "iteration_log": "iteration_log.jsonl",
}


class TaskStore:
    """File-backed state for a single task directory."""

    def __init__(self, task_dir: str | os.PathLike):
        self.task_dir = Path(task_dir)
        self.state_dir = self.task_dir / "state"
        self.logs_dir = self.task_dir / "logs"

    # -- paths ---------------------------------------------------------------
    def path(self, key: str) -> Path:
        return self.state_dir / STATE_FILES[key]

    def ensure_dirs(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    # -- atomic primitives ---------------------------------------------------
    def _atomic_write(self, target: Path, data: str) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f".{target.name}.{ids.pid()}.{ids.new_id()}.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)

    def _append_line(self, target: Path, obj: dict) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(obj, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    # -- task_spec -----------------------------------------------------------
    def write_task_spec(self, markdown: str) -> None:
        self.ensure_dirs()
        with file_lock(self.path("task_spec")):
            self._atomic_write(self.path("task_spec"), markdown)

    def read_task_spec(self) -> str:
        p = self.path("task_spec")
        return p.read_text(encoding="utf-8") if p.exists() else ""

    # -- progress ------------------------------------------------------------
    def read_progress(self) -> Progress | None:
        p = self.path("progress")
        if not p.exists():
            return None
        return Progress.from_dict(json.loads(p.read_text(encoding="utf-8")))

    def write_progress(self, progress: Progress) -> None:
        self.ensure_dirs()
        progress.updated_at = ids.now_iso()
        with file_lock(self.path("progress")):
            self._atomic_write(
                self.path("progress"),
                json.dumps(progress.to_dict(), ensure_ascii=False, indent=2),
            )

    def update_progress(self, **changes) -> Progress:
        """Locked read-modify-write of progress.json."""
        self.ensure_dirs()
        with file_lock(self.path("progress")):
            progress = self.read_progress() or Progress.new(
                changes.get("task_id", self.task_dir.name)
            )
            for key, value in changes.items():
                setattr(progress, key, value)
            progress.updated_at = ids.now_iso()
            self._atomic_write(
                self.path("progress"),
                json.dumps(progress.to_dict(), ensure_ascii=False, indent=2),
            )
            return progress

    def touch_last_seen(self, role: str) -> Progress:
        """Update one role's ``last_seen`` first (B3); creates progress if absent."""
        self.ensure_dirs()
        with file_lock(self.path("progress")):
            progress = self.read_progress() or Progress.new(self.task_dir.name)
            setattr(progress.last_seen, role, ids.now_iso())
            progress.updated_at = ids.now_iso()
            self._atomic_write(
                self.path("progress"),
                json.dumps(progress.to_dict(), ensure_ascii=False, indent=2),
            )
            return progress

    # -- findings (append-only) ---------------------------------------------
    def append_finding(self, finding: Finding) -> None:
        self.ensure_dirs()
        with file_lock(self.path("findings")):
            self._append_line(self.path("findings"), finding.to_dict())

    def read_findings(self, tail: int | None = None) -> list[Finding]:
        p = self.path("findings")
        if not p.exists():
            return []
        lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if tail is not None:
            lines = lines[-tail:]
        return [Finding.from_dict(json.loads(ln)) for ln in lines]

    # -- directions ----------------------------------------------------------
    def read_directions(self) -> list[Direction]:
        p = self.path("directions")
        if not p.exists():
            return []
        return [Direction.from_dict(d) for d in json.loads(p.read_text(encoding="utf-8"))]

    def append_direction(self, direction: Direction) -> None:
        self.ensure_dirs()
        with file_lock(self.path("directions")):
            existing = self.read_directions()
            existing.append(direction)
            self._atomic_write(
                self.path("directions"),
                json.dumps([d.to_dict() for d in existing], ensure_ascii=False, indent=2),
            )

    # -- iteration log -------------------------------------------------------
    def append_iteration_log(self, row: IterationLog) -> None:
        self.ensure_dirs()
        with file_lock(self.path("iteration_log")):
            self._append_line(self.path("iteration_log"), row.to_dict())

    def read_iteration_log(self) -> list[IterationLog]:
        p = self.path("iteration_log")
        if not p.exists():
            return []
        lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
        return [IterationLog.from_dict(json.loads(ln)) for ln in lines]
