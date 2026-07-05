"""Experiment Design sub-skill (§11.1 #3).

Design → Execute (API/GPU) → Iterate (≤5) → Report. Produces results data only;
LaTeX figures are the Figures sub-skill's job.

:class:`ExperimentDesignSkill` encodes the full 4-stage loop with API and GPU
execution paths as a prompt template.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from zhuri.agents.prompt import WorkPrompt, build_prompt
from zhuri.tasks.base import SubSkill, SubSkillContext

MAX_ITERS = 5


@dataclass
class ExperimentReport:
    iterations: int
    succeeded: bool
    results: dict = field(default_factory=dict)


def run_experiment(*, attempt, max_iters: int = MAX_ITERS) -> ExperimentReport:
    """Iterate an experiment up to ``max_iters`` times.

    ``attempt(i)`` returns ``(ok: bool, results: dict)``.
    """
    last: dict = {}
    for i in range(1, max_iters + 1):
        ok, results = attempt(i)
        last = results
        if ok:
            return ExperimentReport(iterations=i, succeeded=True, results=results)
    return ExperimentReport(iterations=max_iters, succeeded=False, results=last)


# ---------------------------------------------------------------------------
# ExperimentDesignSkill — prompt-builder for the work agent
# ---------------------------------------------------------------------------

class ExperimentDesignSkill(SubSkill):
    name = "experiment"
    description = (
        "4-stage experiment loop: Design(hypothesis)→Execute(API/GPU)→"
        "Iterate(≤5)→Report(JSON)"
    )

    def build_prompt(self, ctx: SubSkillContext) -> WorkPrompt:
        return build_prompt(
            background=ctx.task_spec[:3000] or "Design and execute experiments.",
            deliverable=EXPERIMENT_DELIVERABLE,
            working_dir=ctx.extra or ".",
            caps=EXPERIMENT_CAPS,
            completion_criteria=EXPERIMENT_COMPLETION,
            directions_tried=ctx.directions_tried,
            extra=self._findings_extra(ctx),
        )

    @staticmethod
    def _findings_extra(ctx: SubSkillContext) -> str:
        if not ctx.findings:
            return ""
        recent = ctx.findings[-10:]
        return (
            "# Prior experiment/analysis findings\n"
            + "\n".join(f"- {f.claim} :: {f.evidence}" for f in recent)
        )


EXPERIMENT_DELIVERABLE = """Design and execute experiments following the 4-stage loop.

## Stage 1: Design (MOST IMPORTANT — invest effort here)
For each experiment you MUST answer: "Which paper claim does this support?"
- Hypothesis: precise, falsifiable statement
- Independent variables (what you manipulate)
- Dependent variables (what you measure)
- Control variables (what you hold constant)
- Expected results (preregister BEFORE running)
- Statistical test planned: name the test (t-test, ANOVA, bootstrap, etc.) before execution

Design principles:
- Falsifiable: the experiment must be able to FAIL to support the hypothesis
- Minimal first: start with the simplest test, add complexity only when needed
- Has control: every experiment needs a control condition or baseline
- NO HARKing (Hypothesizing After Results are Known)

## Stage 2: Execute — choose your path

### Path A: API (hours, lightweight)
- 3-5 frontier models × 2-3 conditions × 15-25 tasks × 3 trials each
- Use case: multi-model comparison, prompt ablation, benchmarking
- Record: model, prompt, temperature, max_tokens, seed for every call

### Path B: GPU RL (days, heavyweight)
- Cluster job submission with auto-monitoring
- Use case: agent training, reward shaping, RL fine-tuning
- Record: cluster config, GPU hours, hyperparameters, random seeds

## Stage 3: Iterate (max 5 iterations, then accept best result)
| Observation | Action |
|-------------|--------|
| Ceiling effect (all scores near max) | Increase task difficulty |
| Floor effect (all scores near min) | Decrease difficulty or check for bugs |
| Not significant (p > 0.05) | Increase trials or refine hypothesis |
| Surprise finding (unexpected direction) | Design follow-up experiment |
| Consistent across trials | Accept result, move to next hypothesis |

## Stage 4: Report (DATA ONLY — no LaTeX figures or tables)
Output files:
- `results.json`: structured JSON with schema {config, results[task][model][condition], statistics{mean, std, p_value}, findings[string]}
- `experiment_summary.md`: plain-text summary with (1) purpose, (2) key results in bullet points, (3) limitations, (4) links to specific paper claims

CRITICAL: This skill produces RAW DATA. Do NOT generate LaTeX tables or PDF figures — that is the Figures sub-skill's responsibility.
"""

EXPERIMENT_CAPS = (
    "Working directory: results.json + experiment_summary.md. "
    "Max 5 experiment iterations. Max 15 LLM rounds or 30 min."
)

EXPERIMENT_COMPLETION = (
    "Task is complete when: (1) ≥1 hypothesis preregistered, "
    "(2) experiment executed with ≥3 trials per condition, "
    "(3) statistical test reported (p-value or confidence interval), "
    "(4) results.json written with schema-compliant data, "
    "(5) experiment_summary.md written, "
    "(6) no ceiling/floor effect that invalidates results. "
    "Emit FINDING: <claim> :: <evidence> for each experimental result. "
    "Say DONE when complete."
)
