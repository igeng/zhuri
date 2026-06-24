from __future__ import annotations

import inspect

from zhuri.watchdog import liveness


def test_liveness_exposes_only_check_restart_nudge():
    public = {
        name
        for name, obj in vars(liveness).items()
        if not name.startswith("_")
        and inspect.isfunction(obj)
        and obj.__module__ == liveness.__name__
    }
    assert public == {"check", "restart", "nudge"}, public


def test_liveness_all_matches():
    assert set(liveness.__all__) == {"check", "restart", "nudge"}


def test_no_findings_read_in_liveness_source():
    src = inspect.getsource(liveness)
    # B5: liveness must not read findings.
    assert "read_findings" not in src
    assert "findings.jsonl" not in src
