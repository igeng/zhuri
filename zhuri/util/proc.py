"""Safe subprocess spawning with timeout + output capture (§5 util/proc)."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class ProcResult:
    """Result of a finished subprocess."""

    args: list[str]
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out


def run(
    args: list[str],
    *,
    cwd: str | None = None,
    timeout: float | None = None,
    env: dict | None = None,
    input_text: str | None = None,
) -> ProcResult:
    """Run a command to completion, capturing output.

    Never raises on non-zero exit; callers inspect :class:`ProcResult`. A
    timeout produces ``timed_out=True`` and returncode ``-1``.
    """
    try:
        proc = subprocess.run(
            args,
            cwd=cwd,
            env=env,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return ProcResult(
            args=list(args),
            returncode=-1,
            stdout=exc.stdout or "",
            stderr=(exc.stderr or "") + "\n[timeout]",
            timed_out=True,
        )
    except FileNotFoundError as exc:
        return ProcResult(args=list(args), returncode=127, stdout="", stderr=str(exc))
    return ProcResult(
        args=list(args),
        returncode=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
    )


def spawn(
    args: list[str],
    *,
    cwd: str | None = None,
    env: dict | None = None,
    detach: bool = False,
) -> subprocess.Popen:
    """Spawn a background process (used to launch work agents / patrols).

    When ``detach`` is set the child is placed in its own session so it can
    outlive the parent (used for ``--detach`` and L0 install recipes).
    """
    kwargs: dict = {"cwd": cwd, "env": env}
    if detach:
        kwargs["start_new_session"] = True
        kwargs["stdout"] = subprocess.DEVNULL
        kwargs["stderr"] = subprocess.DEVNULL
    return subprocess.Popen(args, **kwargs)
