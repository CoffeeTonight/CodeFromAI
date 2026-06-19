from __future__ import annotations

import json
from pathlib import Path

from soc_verify.graph_session import session_tick, start_session
from soc_verify.beci_formula import assess_node_intervention, beci_vector_from_signals, compute_intervention_urgency
from soc_verify.meta_innovation_loop import build_beci_assessment, validate_reviews
from soc_verify.milestone_pipeline import (
    compile_branch_graph,
    get_pipeline,
    next_pipeline_nodes,
    validate_pipeline_order,
)
from soc_verify.node_scorecard import append_node_scorecard
from soc_verify.schedule_triggers import request_immediate


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "projects" / "EXAMPLE-SOC"


def test_beci_urgency_high_on_env_fail():
    signals = {"completeness": 0.3, "error_kind": "env", "bridge_round": 2, "fix_round": 1}
    events = {"gates_run": 2, "env_fail_steps": 2, "info_interrupts": 1}
    beci = beci_vector_from_signals(signals, events)
    u = compute_intervention_urgency(beci)
    assert u > 0.3
    a = assess_node_intervention(graph_id="verify_group", node_id="run_gate", beci=beci, root=ROOT)
    assert a.urgency == u
    assert list(beci.keys()) == ["B", "E", "C", "I"]


def test_m2_pipeline_order_and_branch():
    pl = get_pipeline(ROOT, "M2_block_sanity")
    assert pl is not None
    ok, issues = validate_pipeline_order(pl, {"c_compile"})
    assert ok
    nxt = next_pipeline_nodes(pl, completed={"c_compile"}, last_verdict="PASS", last_node="c_compile")
    assert "rtl_sim" in nxt
    fail_next = next_pipeline_nodes(pl, completed=set(), last_verdict="FAIL", last_node="c_compile")
    assert fail_next == ["meta_innovation_loop"]
    bg = compile_branch_graph(pl)
    assert bg["entry"] == "c_compile"


def test_node_scorecard_append(tmp_path: Path):
    project = tmp_path / "SC"
    project.mkdir()
    entry = append_node_scorecard(
        project,
        graph_id="verify_group",
        node_id="run_gate",
        run_id="r1",
        signals={"verdict": "FAIL", "completeness": 0.4, "trust_score": 0.5, "error_kind": "env"},
        events={"gates_run": 1, "env_fail_steps": 1},
        root=ROOT,
    )
    assert entry["intervention_urgency"] >= 0
    assert "beci_vector" in entry


def test_meta_innovation_consensus_requires_three_reviews(tmp_path: Path):
    run_dir = tmp_path / "mil"
    run_dir.mkdir()
    (run_dir / "reviewer_a.json").write_text('{"intervene":true,"target_node":"run_gate"}', encoding="utf-8")
    bad = validate_reviews(run_dir, min_reviews=3)
    assert not bad["ok"]
    (run_dir / "reviewer_b.json").write_text('{"intervene":true,"target_node":"run_gate"}', encoding="utf-8")
    (run_dir / "reviewer_c.json").write_text('{"intervene":false,"target_node":""}', encoding="utf-8")
    good = validate_reviews(run_dir, min_reviews=3)
    assert good["ok"]
    assert good["consensus"]["intervene_votes"] == 2


def test_meta_innovation_platform_ticks(tmp_path: Path):
    project = tmp_path / "projects" / "MIL-SOC"
    project.mkdir(parents=True)
    (project / "state.yaml").write_text("schedule_plan: soc-dv-4p-v1\ncurrent_milestone: M2\n", encoding="utf-8")

    started = start_session(tmp_path, graph_id="meta_innovation_loop", project_id="MIL-SOC")
    sid = started["session_id"]

    t1 = session_tick(tmp_path, sid, auto_invoke_llm=False)
    assert t1["tick"] == "ok"
    assert t1["current_node"] == "collect_observations"

    t2 = session_tick(tmp_path, sid, auto_invoke_llm=False)
    assert t2["tick"] == "ok"
    assert t2.get("completed_node") == "collect_observations"

    t3 = session_tick(tmp_path, sid, auto_invoke_llm=False)
    assert t3["tick"] == "ok"
    assert t3.get("completed_node") == "beci_assess"

    st = t3
    run_dir = project / "runs" / "meta_innovation" / st["state"]["run_id"]
    assert (run_dir / "observations.json").is_file()
    assert (run_dir / "beci_assessment.json").is_file()


def test_request_immediate_trigger(tmp_path: Path):
    project = tmp_path / "P"
    project.mkdir()
    request_immediate(project)
    from soc_verify.schedule_triggers import load_project_schedule

    sched = load_project_schedule(project)
    assert sched.get("meta_innovation_loop", {}).get("run_now")