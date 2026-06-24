from __future__ import annotations

import pytest

from zhuri.agents.prompt import PromptIncompleteError, build_prompt


def _full(**over):
    args = dict(
        background="bg",
        deliverable="del",
        working_dir="/tmp/x",
        caps="<=15 rounds",
        completion_criteria="done when X",
    )
    args.update(over)
    return build_prompt(**args)


def test_build_prompt_ok():
    p = _full()
    assert "# Background" in p.user
    assert "Deliverable" in p.user
    assert "B1" in p.system or "zero-interaction" in p.system


@pytest.mark.parametrize(
    "field", ["background", "deliverable", "working_dir", "caps", "completion_criteria"]
)
def test_missing_field_rejected(field):
    with pytest.raises(PromptIncompleteError) as ei:
        _full(**{field: "   "})
    assert field in str(ei.value)


def test_directions_tried_rendered():
    p = _full(directions_tried=["axis-a", "axis-b"])
    assert "axis-a" in p.user and "axis-b" in p.user
