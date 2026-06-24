"""State dataclasses (§6.4 schemas)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from ..util import ids

STATUSES = ("idle", "running", "stalled", "pivoting", "escalated", "done")


@dataclass
class LastSeen:
    """Per-role liveness timestamps (B3)."""

    work: str | None = None
    orchestrator: str | None = None
    heartbeat: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict | None) -> "LastSeen":
        data = data or {}
        return cls(
            work=data.get("work"),
            orchestrator=data.get("orchestrator"),
            heartbeat=data.get("heartbeat"),
        )


@dataclass
class Progress:
    """`progress.json` model."""

    task_id: str
    iteration: int = 0
    status: str = "idle"
    total_findings: int = 0
    stale_count: int = 0
    last_metric: float | None = None
    last_seen: LastSeen = field(default_factory=LastSeen)
    updated_at: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        data["last_seen"] = self.last_seen.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Progress":
        return cls(
            task_id=data["task_id"],
            iteration=data.get("iteration", 0),
            status=data.get("status", "idle"),
            total_findings=data.get("total_findings", 0),
            stale_count=data.get("stale_count", 0),
            last_metric=data.get("last_metric"),
            last_seen=LastSeen.from_dict(data.get("last_seen")),
            updated_at=data.get("updated_at", ""),
        )

    @classmethod
    def new(cls, task_id: str) -> "Progress":
        return cls(task_id=task_id, updated_at=ids.now_iso())


@dataclass
class Finding:
    """`findings.jsonl` line."""

    claim: str
    evidence: str
    iteration: int
    verifiable: bool = True
    source: str = ""
    ts: str = field(default_factory=ids.now_iso)

    def to_dict(self) -> dict:
        return {
            "ts": self.ts,
            "iteration": self.iteration,
            "claim": self.claim,
            "evidence": self.evidence,
            "verifiable": self.verifiable,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Finding":
        return cls(
            claim=data["claim"],
            evidence=data.get("evidence", ""),
            iteration=data.get("iteration", 0),
            verifiable=data.get("verifiable", True),
            source=data.get("source", ""),
            ts=data.get("ts", ids.now_iso()),
        )


@dataclass
class Direction:
    """`directions_tried.json` element (diversity basis, §7.4)."""

    iteration: int
    direction: str
    structural_axis: str
    result: str = "stall"  # stall|gain
    ts: str = field(default_factory=ids.now_iso)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Direction":
        return cls(
            iteration=data.get("iteration", 0),
            direction=data["direction"],
            structural_axis=data.get("structural_axis", ""),
            result=data.get("result", "stall"),
            ts=data.get("ts", ids.now_iso()),
        )


@dataclass
class IterationLog:
    """`iteration_log.jsonl` per-iteration summary row."""

    iteration: int
    direction: str
    new_findings: int
    metric: float | None
    validated: bool
    result: str  # stall|gain
    ts: str = field(default_factory=ids.now_iso)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "IterationLog":
        return cls(
            iteration=data.get("iteration", 0),
            direction=data.get("direction", ""),
            new_findings=data.get("new_findings", 0),
            metric=data.get("metric"),
            validated=data.get("validated", False),
            result=data.get("result", "stall"),
            ts=data.get("ts", ids.now_iso()),
        )
