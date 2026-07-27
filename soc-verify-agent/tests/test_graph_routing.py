from __future__ import annotations

import pytest

from soc_verify.graph_spec import load_flow_spec, next_nodes_from_spec, topology_from_spec
from soc_verify.graphs.verify_routing import route_after_finalize
from soc_verify.graphs.verify_group import (
    route_after_apply_validation,
    route_after_run,
    route_after_eval,
    route_after_diagnose,
    route_after_load,
    route_after_parity,
)
from soc_verify.validation_autonomy import _mechanical_judgment

ROOT = pytest.importorskip("pathlib").Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "projects" / "EXAMPLE-SOC"


def _assert_route_in_spec(graph_id: str, node_id: str, destination: str) -> None:
    spec = load_flow_spec(ROOT)
    allowed = next_nodes_from_spec(spec, graph_id, node_id)
    assert destination in allowed, f"{node_id} → {destination} not in spec edges {allowed}"


@pytest.mark.parametrize(
    "state,expected",
    [
        ({"verdict": "FAIL", "error_kind": "verification"}, "parse_validation_items"),
        ({"verdict": "FAIL", "error_kind": "env"}, "diagnose_env"),
        ({"verdict": "PASS", "error_kind": "none"}, "evaluate"),
        ({"info_gap": True, "error_kind": "info"}, "finalize"),
        ({"info_gap": True, "verdict": "INFO_GAP"}, "finalize"),
    ],
)
def test_route_after_run_matches_spec(state: dict, expected: str) -> None:
    assert route_after_run(state) == expected
    _assert_route_in_spec("verify_group", "run_gate", expected)


@pytest.mark.parametrize(
    "state,expected",
    [
        ({"validation_sequence_action": "retry_gate"}, "select_runner"),
        ({"validation_sequence_action": "retry_gate", "verdict": "FAIL"}, "select_runner"),
        (
            {
                "validation_sequence_action": "continue_remaining",
                "verdict": "FAIL",
                "validation_judgment": {"source": "llm", "sequence_action": "continue_remaining"},
            },
            "finalize",
        ),
        (
            {
                "validation_sequence_action": "continue_remaining",
                "verdict": "PASS",
                "validation_judgment": {"source": "llm", "sequence_action": "continue_remaining"},
            },
            "evaluate",
        ),
        ({"validation_sequence_action": "halt", "verdict": "FAIL"}, "finalize"),
    ],
)
def test_route_after_apply_validation_matches_spec(state: dict, expected: str) -> None:
    assert route_after_apply_validation(state) == expected
    _assert_route_in_spec("verify_group", "run_pending_repro", expected)


def test_topology_from_spec_matches_verify_group_routing() -> None:
    spec = load_flow_spec(ROOT)
    topo = topology_from_spec(spec, "verify_group")
    assert "run_pending_repro" in topo["nodes"]
    assert topo["edges"]["apply_validation_plan"] == ["run_pending_repro"]
    assert set(topo["edges"]["run_pending_repro"]) == {"select_runner", "evaluate", "finalize"}


def test_mechanical_judgment_defaults_retry_gate() -> None:
    payload = {
        "stage": "simulation",
        "group": "slave_rw",
        "items": [{"item_id": "sim_burst", "status": "fail", "actual": "2 failed"}],
    }
    j = _mechanical_judgment(payload)
    assert j["sequence_action"] == "retry_gate"
    assert j["source"] == "mechanical"


def test_route_after_eval_pass_goes_parity() -> None:
    dest = route_after_eval({"verdict": "PASS", "open_issues": 0, "continue_improvement": False})
    assert dest == "parity_check"
    _assert_route_in_spec("verify_group", "evaluate", dest)


def test_route_after_load_info_gap() -> None:
    assert route_after_load({"info_gap": True}) == "finalize"
    _assert_route_in_spec("verify_group", "load_context", "finalize")


def test_route_after_diagnose_patch() -> None:
    assert route_after_diagnose({"error": ""}) == "patch_bridge"
    _assert_route_in_spec("verify_group", "diagnose_env", "patch_bridge")


def test_route_after_diagnose_after_env_fail_realistic_state() -> None:
    """Post run_gate env fail: verdict FAIL, error unset until diagnose clears it."""
    state = {
        "verdict": "FAIL",
        "error_kind": "env",
        "error": "",
        "project_dir": str(EXAMPLE),
        "run_id": "r1",
    }
    assert route_after_diagnose(state) == "patch_bridge"


def test_route_after_diagnose_bridge_cap() -> None:
    state = {
        "error": "bridge_round_cap",
        "project_dir": str(EXAMPLE),
        "run_id": "r1",
    }
    assert route_after_diagnose(state) == "finalize"


def test_route_after_parity_ok() -> None:
    assert route_after_parity({"parity_ok": True}) == "promote"
    _assert_route_in_spec("verify_group", "parity_check", "promote")


def test_route_after_parity_codegen_cap_finalizes() -> None:
    state = {
        "verdict": "PASS",
        "parity_ok": False,
        "error": "codegen_round_cap",
        "project_dir": str(EXAMPLE),
        "run_id": "r1",
    }
    assert route_after_parity(state) == "finalize"
    _assert_route_in_spec("verify_group", "parity_check", "finalize")


def test_route_after_parity_info_gap_finalizes() -> None:
    state = {
        "info_gap": True,
        "parity_ok": False,
        "error_kind": "info",
        "project_dir": str(EXAMPLE),
        "run_id": "r1",
    }
    assert route_after_parity(state) == "finalize"


def test_route_after_run_spinning_stalemate_env_still_diagnoses() -> None:
    run_dir = EXAMPLE / "runs" / "spinning-env-test"
    run_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "verdict": "FAIL",
        "error_kind": "env",
        "stalemate": True,
        "stalemate_pattern": "SPINNING",
        "project_dir": str(EXAMPLE),
        "run_id": "spinning-env-test",
    }
    assert route_after_run(state) == "diagnose_env"
    _assert_route_in_spec("verify_group", "run_gate", "diagnose_env")


def test_route_after_diagnose_success_with_stalemate_patches() -> None:
    state = {
        "error": "",
        "stalemate": True,
        "stalemate_pattern": "OSCILLATION",
        "project_dir": str(EXAMPLE),
        "run_id": "r1",
    }
    assert route_after_diagnose(state) == "patch_bridge"
    _assert_route_in_spec("verify_group", "diagnose_env", "patch_bridge")


def test_route_after_run_oscillation_stalemate_goes_validation() -> None:
    state = {
        "verdict": "FAIL",
        "error_kind": "verification",
        "stalemate": True,
        "stalemate_pattern": "OSCILLATION",
        "project_dir": str(EXAMPLE),
        "run_id": "r1",
    }
    assert route_after_run(state) == "parse_validation_items"


def test_route_after_eval_no_drift_with_open_issues_retries() -> None:
    state = {
        "verdict": "FAIL",
        "open_issues": 1,
        "stalemate": True,
        "stalemate_pattern": "NO_DRIFT",
        "project_dir": str(EXAMPLE),
        "run_id": "r1",
    }
    assert route_after_eval(state) == "select_runner"
    _assert_route_in_spec("verify_group", "evaluate", "select_runner")


def test_route_after_finalize_training_skips_meta() -> None:
    state = {
        "project_dir": str(EXAMPLE),
        "run_profile": "training",
    }
    assert route_after_finalize(state) == "end"


def test_route_after_finalize_production_runs_meta() -> None:
    state = {
        "project_dir": str(EXAMPLE),
        "run_profile": "production",
    }
    assert route_after_finalize(state) == "meta_collect"
    _assert_route_in_spec("verify_group", "finalize", "meta_collect")


def test_route_after_eval_stalemate_no_drift_finalizes() -> None:
    state = {
        "verdict": "PASS",
        "open_issues": 0,
        "stalemate": True,
        "stalemate_pattern": "NO_DRIFT",
        "project_dir": str(EXAMPLE),
        "run_id": "r1",
    }
    assert route_after_eval(state) == "finalize"
    _assert_route_in_spec("verify_group", "evaluate", "finalize")


def test_route_after_apply_validation_reads_judgment_file() -> None:
    run_dir = EXAMPLE / "runs" / "judgment-test"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "validation_judgment.json").write_text(
        '{"contract":"validation_judgment_v1","sequence_action":"retry_gate","source":"mechanical"}',
        encoding="utf-8",
    )
    state = {
        "verdict": "FAIL",
        "project_dir": str(EXAMPLE),
        "run_id": "judgment-test",
    }
    assert route_after_apply_validation(state) == "select_runner"


def test_route_after_apply_validation_file_overrides_stale_state() -> None:
    run_dir = EXAMPLE / "runs" / "judgment-stale"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "validation_judgment.json").write_text(
        '{"contract":"validation_judgment_v1","sequence_action":"retry_gate","source":"mechanical"}',
        encoding="utf-8",
    )
    state = {
        "verdict": "FAIL",
        "project_dir": str(EXAMPLE),
        "run_id": "judgment-stale",
        "validation_judgment": {
            "contract": "validation_judgment_v1",
            "sequence_action": "halt",
            "source": "llm",
        },
    }
    assert route_after_apply_validation(state) == "select_runner"


def test_route_after_eval_stalemate_oscillation_retries() -> None:
    state = {
        "verdict": "PASS",
        "open_issues": 0,
        "stalemate": True,
        "stalemate_pattern": "OSCILLATION",
        "project_dir": str(EXAMPLE),
        "run_id": "r1",
    }
    assert route_after_eval(state) == "select_runner"
    _assert_route_in_spec("verify_group", "evaluate", "select_runner")