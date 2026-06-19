from __future__ import annotations

from pathlib import Path

from soc_verify.node_triage import evaluate_node_outcome, resolve_route

ROOT = Path(__file__).resolve().parents[1]


def test_diagnose_env_outcome_pass_after_env_fail_verdict(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    state = {
        "project_dir": str(tmp_path),
        "run_id": "run",
        "verdict": "FAIL",
        "error_kind": "env",
        "error": "",
    }
    outcome = evaluate_node_outcome(
        ROOT, "verify_group", "diagnose_env", state=state, run_dir=run_dir
    )
    assert outcome.outcome == "pass"
    route = resolve_route(ROOT, "verify_group", "diagnose_env", state, run_dir=run_dir)
    assert route == "patch_bridge"


def test_diagnose_env_outcome_bridge_cap(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    state = {
        "project_dir": str(tmp_path),
        "run_id": "run",
        "error": "bridge_round_cap",
    }
    outcome = evaluate_node_outcome(
        ROOT, "verify_group", "diagnose_env", state=state, run_dir=run_dir
    )
    assert outcome.outcome == "fail"
    assert outcome.fail_class == "bridge_cap"
    route = resolve_route(ROOT, "verify_group", "diagnose_env", state, run_dir=run_dir)
    assert route == "finalize"