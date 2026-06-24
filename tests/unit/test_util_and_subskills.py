from __future__ import annotations

import datetime as _dt

from zhuri.util import ids, proc
from zhuri.tasks.paper_writing.subskills import experiment, figures, structure


def test_proc_run_ok():
    r = proc.run(["python", "-c", "print('hi')"])
    assert r.ok and "hi" in r.stdout


def test_proc_run_nonzero():
    r = proc.run(["python", "-c", "import sys; sys.exit(3)"])
    assert r.returncode == 3 and not r.ok


def test_proc_run_timeout():
    r = proc.run(["python", "-c", "import time; time.sleep(5)"], timeout=0.2)
    assert r.timed_out and not r.ok


def test_proc_run_not_found():
    r = proc.run(["definitely-not-a-real-binary-xyz"])
    assert r.returncode == 127


def test_proc_spawn():
    p = proc.spawn(["python", "-c", "pass"])
    assert p.wait(timeout=10) == 0


def test_ids_seed_deterministic():
    ids.seed(42)
    a = [ids.new_id("x") for _ in range(3)]
    ids.seed(42)
    b = [ids.new_id("x") for _ in range(3)]
    assert a == b


def test_ids_freeze_time():
    when = _dt.datetime(2030, 1, 1, tzinfo=_dt.timezone.utc)
    ids.freeze_time(when)
    assert ids.now() == when
    assert ids.now_iso().startswith("2030-01-01")
    ids.freeze_time(None)


def test_ids_slugify_and_auto():
    assert ids.slugify("Hello, World!!") == "hello-world"
    assert ids.slugify("") == "task"
    assert ids.auto_task_id("Study Agents").startswith("study-agents")


def test_experiment_iterates_until_success():
    rep = experiment.run_experiment(attempt=lambda i: (i == 2, {"i": i}))
    assert rep.succeeded and rep.iterations == 2


def test_experiment_fails_after_max():
    rep = experiment.run_experiment(attempt=lambda i: (False, {"i": i}), max_iters=3)
    assert not rep.succeeded and rep.iterations == 3


def test_figures_booktabs_and_error_bars():
    table = figures.booktabs_table(["a", "b"], [[1, 2]])
    assert "\\toprule" in table and "1 & 2" in table
    assert figures.figure_has_error_bars({"mean": 1, "std": 0.1})
    assert not figures.figure_has_error_bars({"mean": 1})


def test_structure_hedge_already_hedged():
    assert structure.hedge_claim("We suggest X works").endswith(".")
