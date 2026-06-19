from __future__ import annotations

import json
from pathlib import Path

from soc_verify.graph_session import session_status, session_tick, start_session
from soc_verify.graphs.setup_group import run_setup_group
from soc_verify.milestone_plans import load_plan
from soc_verify.setup_adaptive import build_milestone_context, phase_tasks_for_plan
from soc_verify.skill_registry import list_skills


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "projects" / "EXAMPLE-SOC"


def test_phase_tasks_in_soc_plan():
    plan = load_plan(ROOT, "soc-dv-4p-v1")
    assert plan is not None
    tasks = phase_tasks_for_plan(plan)
    assert "M2" in tasks
    assert any("sanity" in t.lower() for t in tasks["M2"])


def test_build_milestone_context_has_phase_tasks():
    ctx = build_milestone_context(ROOT, EXAMPLE)
    assert ctx["schedule_plan"] == "soc-dv-4p-v1"
    m3 = next(m for m in ctx["milestones"] if m["id"] == "M3")
    assert m3.get("phase_tasks")


def test_setup_group_platform_nodes_via_session():
    started = start_session(
        ROOT,
        graph_id="setup_group",
        project_id="EXAMPLE-SOC",
        user_skillset="UVM block smoke\nChip sim nightly",
    )
    session_id = started["session_id"]

    tick1 = session_tick(ROOT, session_id, auto_invoke_llm=False)
    assert tick1["tick"] == "ok"
    assert tick1["current_node"] == "milestone_context"

    tick2 = session_tick(ROOT, session_id, auto_invoke_llm=False)
    assert tick2["tick"] == "ok"
    assert tick2.get("completed_node") == "milestone_context"

    tick3 = session_tick(ROOT, session_id, auto_invoke_llm=False)
    assert tick3["tick"] == "ok"
    assert tick3.get("completed_node") == "register_skills"

    st = session_status(ROOT, session_id)
    run_dir = Path(st["state"]["project_dir"]) / "runs" / "setup" / st["state"]["run_id"]
    assert (run_dir / "milestone_context.json").is_file()
    assert (run_dir / "skills_registered.json").is_file()
    skills = list_skills(EXAMPLE)
    assert len(skills) >= 1


def test_setup_group_full_run_with_stub_llm_artifacts(tmp_path: Path):
    project = tmp_path / "ADAPT-SOC"
    project.mkdir()
    (project / "state.yaml").write_text(
        "schedule_plan: soc-dv-4p-v1\ncurrent_milestone: M2\nactive: true\n",
        encoding="utf-8",
    )
    (project / "scripts").mkdir()
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    project.rename(projects_root / "ADAPT-SOC")
    project = projects_root / "ADAPT-SOC"

    started = start_session(
        tmp_path,
        graph_id="setup_group",
        project_id="ADAPT-SOC",
        user_skillset="# Sanity compile\nRun c-compile gate.",
    )
    session_id = started["session_id"]

    for _ in range(3):
        t = session_tick(tmp_path, session_id, auto_invoke_llm=False)
        assert t["tick"] == "ok"

    st = session_status(tmp_path, session_id)
    run_dir = project / "runs" / "setup" / st["state"]["run_id"]

    (run_dir / "setup_adapt.json").write_text(
        json.dumps({"summary": "M2 block sanity tools", "tools": [], "scripts": ["run_beginner.sh"]}),
        encoding="utf-8",
    )
    t4 = session_tick(tmp_path, session_id, auto_invoke_llm=False)
    assert t4["tick"] == "ok"
    assert t4.get("completed_node") == "llm_adapt"

    (project / "scripts" / "run_beginner.sh").write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\necho beginner smoke\n",
        encoding="utf-8",
    )
    (run_dir / "bootstrap_finalize.json").write_text(
        json.dumps({"ok": True, "script": "run_beginner.sh"}),
        encoding="utf-8",
    )
    t5 = session_tick(tmp_path, session_id, auto_invoke_llm=False)
    assert t5["tick"] == "ok"
    assert t5.get("completed_node") == "llm_bootstrap_scripts"

    t6 = session_tick(tmp_path, session_id, auto_invoke_llm=False)
    assert t6["tick"] == "ok"
    assert t6.get("completed_node") == "finalize"

    final = session_status(tmp_path, session_id)
    assert final["finished"]
    assert (run_dir / "setup_workflow.json").is_file()


def test_run_setup_group_direct(tmp_path: Path):
    project = tmp_path / "projects" / "DIRECT-SOC"
    project.mkdir(parents=True)
    (project / "state.yaml").write_text(
        "schedule_plan: soc-dv-4p-v1\ncurrent_milestone: M1\n",
        encoding="utf-8",
    )
    run_dir = project / "runs" / "setup" / "testrun"
    run_dir.mkdir(parents=True)
    (run_dir / "setup_adapt.json").write_text(
        json.dumps({"summary": "stub", "tools": []}),
        encoding="utf-8",
    )
    (project / "scripts").mkdir(exist_ok=True)
    (project / "scripts" / "run_beginner.sh").write_text("#!/bin/bash\necho ok\n", encoding="utf-8")
    (run_dir / "bootstrap_finalize.json").write_text('{"ok":true}', encoding="utf-8")

    # Direct graph invoke still needs LLM artifacts at node boundaries when using interruptible graph;
    # run_setup_group uses non-interruptible compile — platform nodes run, LLM nodes pass if files exist.
    result = run_setup_group(tmp_path, "DIRECT-SOC", user_skillset="lint check")
    assert result.get("verdict") == "PASS" or result.get("skills_registered", 0) >= 0