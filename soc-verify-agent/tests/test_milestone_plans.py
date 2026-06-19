from __future__ import annotations

from pathlib import Path

from soc_verify.milestone_gate import check_milestone_gate, milestone_index
from soc_verify.milestone_plans import (
    list_plans,
    load_plan,
    resolve_schedule_context,
    validate_project_schedule,
)


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "projects" / "EXAMPLE-SOC"


def test_list_plans_includes_soc_and_agile():
    plans = list_plans(ROOT)
    ids = {p["id"] for p in plans}
    assert "soc-dv-4p-v1" in ids
    assert "agile-3p-v1" in ids
    assert "custom" in ids


def test_soc_dv_gate_still_blocks_future():
    state = {"schedule_plan": "soc-dv-4p-v1", "current_milestone": "M2"}
    ok, msg = check_milestone_gate({"milestone": "M4"}, state, root=ROOT)
    assert not ok
    assert "ahead" in msg


def test_agile_plan_gate():
    state = {
        "schedule_plan": "agile-3p-v1",
        "current_milestone": "B1",
        "milestones": [
            {"id": "D1", "label": "Discover"},
            {"id": "B1", "label": "Build"},
            {"id": "R1", "label": "Release"},
        ],
    }
    ok, _ = check_milestone_gate({"milestone": "B1"}, state, root=ROOT)
    assert ok
    ok2, msg2 = check_milestone_gate({"milestone": "R1"}, state, root=ROOT)
    assert not ok2
    assert "ahead" in msg2


def test_custom_inline_milestones():
    state = {
        "schedule_plan": "custom",
        "current_milestone": "Sprint-2",
        "milestones": [
            {"id": "Sprint-1", "label": "Kickoff"},
            {"id": "Sprint-2", "label": "Integration"},
            {"id": "Sprint-3", "label": "Sign-off"},
        ],
    }
    ctx = resolve_schedule_context(state, ROOT)
    assert ctx.plan_id == "custom"
    assert ctx.ordered_ids == ["Sprint-1", "Sprint-2", "Sprint-3"]
    ok, _ = check_milestone_gate({"milestone": "Sprint-2"}, state, root=ROOT)
    assert ok
    assert milestone_index("Sprint-2", state=state, root=ROOT) == 1


def test_validate_example_soc():
    result = validate_project_schedule(ROOT, EXAMPLE)
    assert result["schedule"]["plan_id"] == "soc-dv-4p-v1"
    assert result["valid"] is True


def test_load_agile_plan():
    plan = load_plan(ROOT, "agile-3p-v1")
    assert plan is not None
    ids = [m["id"] for m in plan["milestones"]]
    assert ids == ["D1", "B1", "R1"]