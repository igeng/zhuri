from __future__ import annotations

import json
import threading

from zhuri.state.models import Direction, Finding, IterationLog, Progress
from zhuri.state.store import TaskStore


def test_progress_roundtrip(task_dir):
    store = TaskStore(task_dir)
    prog = Progress.new("task-001")
    store.write_progress(prog)
    loaded = store.read_progress()
    assert loaded.task_id == "task-001"
    assert loaded.status == "idle"
    assert loaded.last_seen.work is None


def test_touch_last_seen_creates_and_updates(task_dir):
    store = TaskStore(task_dir)
    prog = store.touch_last_seen("work")
    assert prog.last_seen.work is not None
    assert prog.last_seen.orchestrator is None


def test_findings_append_only(task_dir):
    store = TaskStore(task_dir)
    store.append_finding(Finding(claim="a", evidence="e", iteration=1))
    store.append_finding(Finding(claim="b", evidence="e", iteration=1))
    findings = store.read_findings()
    assert [f.claim for f in findings] == ["a", "b"]
    assert store.read_findings(tail=1)[0].claim == "b"


def test_directions_and_iteration_log(task_dir):
    store = TaskStore(task_dir)
    store.append_direction(Direction(iteration=1, direction="d1", structural_axis="axis"))
    store.append_iteration_log(
        IterationLog(iteration=1, direction="d1", new_findings=2, metric=1.0,
                     validated=True, result="gain")
    )
    assert store.read_directions()[0].direction == "d1"
    assert store.read_iteration_log()[0].new_findings == 2


def test_atomic_progress_no_partial(task_dir):
    store = TaskStore(task_dir)
    store.write_progress(Progress.new("task-001"))
    raw = store.path("progress").read_text()
    json.loads(raw)  # must always be valid JSON


def test_concurrent_updates_no_corruption(task_dir):
    store = TaskStore(task_dir)
    store.write_progress(Progress.new("task-001"))

    def bump():
        for _ in range(20):
            with __import__("zhuri.state.locks", fromlist=["file_lock"]).file_lock(
                store.path("progress")
            ):
                prog = store.read_progress()
                prog.total_findings += 1
                store._atomic_write(
                    store.path("progress"),
                    json.dumps(prog.to_dict(), ensure_ascii=False, indent=2),
                )

    threads = [threading.Thread(target=bump) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert store.read_progress().total_findings == 80
