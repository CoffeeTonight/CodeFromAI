from __future__ import annotations

import json
from pathlib import Path

from soc_verify.node_gate import finalize_node_gate
from soc_verify.node_triage import (
    evaluate_node_outcome,
    load_llm_triage_plan,
    record_outcome_and_strategy,
    resolve_route,
    resolve_strategy,
    save_user_triage_override,
    write_triage_plan,
)

ROOT = Path(__file__).resolve().parents[1]


def test_evaluate_node_outcome_run_gate_pass(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    state = {
        "project_dir": str(tmp_path),
        "run_id": "run",
        "verdict": "PASS",
        "error_kind": "none",
    }
    outcome = evaluate_node_outcome(
        ROOT, "verify_group", "run_gate", state=state, run_dir=run_dir
    )
    assert outcome.outcome == "pass"


def test_evaluate_node_outcome_run_gate_env_fail(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    state = {
        "project_dir": str(tmp_path),
        "run_id": "run",
        "verdict": "FAIL",
        "error_kind": "env",
    }
    outcome = evaluate_node_outcome(
        ROOT, "verify_group", "run_gate", state=state, run_dir=run_dir
    )
    assert outcome.outcome == "fail"
    assert outcome.fail_class == "env"


def test_resolve_route_run_gate_matches_spec(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    state = {
        "project_dir": str(tmp_path),
        "run_id": "run",
        "verdict": "FAIL",
        "error_kind": "verification",
    }
    route = resolve_route(ROOT, "verify_group", "run_gate", state, run_dir=run_dir)
    assert route == "parse_validation_items"


def test_resolve_route_validation_sequence_action(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    state = {
        "project_dir": str(tmp_path),
        "run_id": "run",
        "validation_sequence_action": "retry_gate",
        "verdict": "FAIL",
    }
    route = resolve_route(ROOT, "verify_group", "run_pending_repro", state, run_dir=run_dir)
    assert route == "select_runner"


def test_resolve_route_evaluate_if_pass_else_finalize(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    state = {
        "project_dir": str(tmp_path),
        "run_id": "run",
        "validation_sequence_action": "continue_remaining",
        "verdict": "PASS",
    }
    route = resolve_route(ROOT, "verify_group", "run_pending_repro", state, run_dir=run_dir)
    assert route == "evaluate"


def test_llm_triage_plan_overrides_platform(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    write_triage_plan(
        run_dir,
        node_id="run_gate",
        fail_class="env",
        route="finalize",
        rationale_ko="LLM override",
        source="llm",
    )
    state = {
        "project_dir": str(tmp_path),
        "run_id": "run",
        "verdict": "FAIL",
        "error_kind": "env",
    }
    strategy = resolve_strategy(
        ROOT,
        "verify_group",
        "run_gate",
        outcome=evaluate_node_outcome(
            ROOT, "verify_group", "run_gate", state=state, run_dir=run_dir
        ),
        state=state,
        run_dir=run_dir,
    )
    assert strategy["source"] == "llm"
    assert strategy["route"] == "finalize"


def test_user_triage_override(tmp_path: Path):
    project = tmp_path / "projects" / "P1"
    run_dir = project / "runs" / "r1"
    run_dir.mkdir(parents=True)
    save_user_triage_override(
        project,
        "verify_group",
        "run_gate",
        fail_routes={"env": "finalize"},
    )
    state = {
        "project_dir": str(project),
        "run_id": "r1",
        "verdict": "FAIL",
        "error_kind": "env",
    }
    route = resolve_route(ROOT, "verify_group", "run_gate", state, run_dir=run_dir)
    assert route == "finalize"


def test_finalize_node_gate_records_outcome(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    group = "gpio_ext"
    (run_dir / f"verdict_{group}.json").write_text(
        json.dumps({"status": "PASS", "gate": group}),
        encoding="utf-8",
    )
    (run_dir / "graph_step.json").write_text("{}", encoding="utf-8")
    (run_dir / "graph_trace.jsonl").write_text(
        json.dumps({"node": "run_gate"}) + "\n",
        encoding="utf-8",
    )
    state = {
        "project_id": "P1",
        "project_dir": str(tmp_path),
        "stage": "simulation",
        "group": group,
        "runner": "python",
        "run_id": "run",
        "error_kind": "none",
        "verdict": "PASS",
        "events": {"gates_run": 1},
    }
    result = finalize_node_gate(
        ROOT,
        "verify_group",
        "run_gate",
        state=state,
        run_dir=run_dir,
        summary_ko="gate PASS",
    )
    assert result.ok
    pass_path = run_dir / "node_gate" / "run_gate_pass.json"
    data = json.loads(pass_path.read_text(encoding="utf-8"))
    assert data["outcome"]["outcome"] == "pass"
    assert data["strategy"]["route"] == "evaluate"
    assert load_llm_triage_plan(run_dir, "run_gate") is None


def test_record_outcome_writes_platform_plan_on_fail(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    state = {
        "project_dir": str(tmp_path),
        "run_id": "run",
        "verdict": "FAIL",
        "error_kind": "env",
    }
    record_outcome_and_strategy(
        ROOT,
        "verify_group",
        "run_gate",
        state=state,
        run_dir=run_dir,
    )
    plan = load_llm_triage_plan(run_dir, "run_gate")
    assert plan is not None
    assert plan["route"] == "diagnose_env"
    assert plan["source"] == "platform"