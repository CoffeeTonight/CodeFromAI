from __future__ import annotations

import json
import uuid
from pathlib import Path

from soc_verify.graph_session import session_sandbox, session_tick, start_session
from soc_verify.node_contract import (
    load_node_contract,
    node_contract_block,
    path_allowed_for_node,
    validate_exit_contract,
    validate_transition,
)
from soc_verify.tool_sandbox import validate_tool_invoke, validate_write_path


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "projects" / "EXAMPLE-SOC"


def test_node_contract_loads_run_gate_tools():
    contract = load_node_contract(ROOT)
    block = node_contract_block(contract, "verify_group", "run_gate")
    assert block is not None
    assert "compile" in block.get("allowed_tools", [])
    assert "write_ops" in block.get("forbidden_actions", [])


def test_validate_transition_illegal_edge():
    result = validate_transition(ROOT, "verify_group", "evaluate", "promote")
    assert result.ok is False
    assert "parity_check" in str(result.issues)


def test_validate_transition_legal_pass_to_parity():
    result = validate_transition(ROOT, "verify_group", "evaluate", "parity_check")
    assert result.ok is True


def test_exit_contract_run_gate_blocks_without_artifacts(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    state = {
        "project_id": "EXAMPLE-SOC",
        "project_dir": str(EXAMPLE),
        "stage": "simulation",
        "group": "gpio_ext",
        "runner": "llm",
    }
    result = validate_exit_contract(
        ROOT,
        "verify_group",
        "run_gate",
        state=state,
        run_dir=run_dir,
    )
    assert result.ok is False
    assert result.issues


def test_exit_contract_run_gate_passes_with_verdict(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    group = "gpio_ext"
    (run_dir / f"verdict_{group}.json").write_text(
        json.dumps({"status": "PASS", "gate": group}),
        encoding="utf-8",
    )
    state = {
        "project_id": "EXAMPLE-SOC",
        "project_dir": str(EXAMPLE),
        "stage": "simulation",
        "group": group,
        "runner": "llm",
    }
    result = validate_exit_contract(
        ROOT,
        "verify_group",
        "run_gate",
        state=state,
        run_dir=run_dir,
    )
    assert result.ok is True


def test_path_allowed_for_run_gate_run_dir_only():
    run_rel = EXAMPLE / "runs" / "sandbox-test" / "verdict_gpio_ext.json"
    ok, _ = path_allowed_for_node(
        ROOT,
        "verify_group",
        "run_gate",
        run_rel,
        project_dir=EXAMPLE,
    )
    assert ok is True


def test_path_denied_registry_for_run_gate():
    reg = EXAMPLE / "trust" / "registry.yaml"
    ok, reason = path_allowed_for_node(
        ROOT,
        "verify_group",
        "run_gate",
        reg,
        project_dir=EXAMPLE,
    )
    assert ok is False
    assert "globs" in reason or "not" in reason


def test_tool_sandbox_denies_write_ops_at_run_gate():
    state = {
        "project_id": "EXAMPLE-SOC",
        "project_dir": str(EXAMPLE),
        "stage": "simulation",
        "group": "gpio_ext",
        "runner": "llm",
    }
    result = validate_tool_invoke(
        ROOT,
        session_id="test-session",
        graph_id="verify_group",
        node_id="run_gate",
        tool_name="write_ops",
        state=state,
    )
    assert result.ok is False


def test_tool_sandbox_allows_compile_at_run_gate():
    state = {
        "project_id": "EXAMPLE-SOC",
        "project_dir": str(EXAMPLE),
        "stage": "simulation",
        "group": "gpio_ext",
        "runner": "llm",
    }
    result = validate_tool_invoke(
        ROOT,
        session_id="test-session",
        graph_id="verify_group",
        node_id="run_gate",
        tool_name="compile",
        state=state,
    )
    assert result.ok is True


def test_session_status_includes_node_sandbox():
    started = start_session(
        ROOT,
        graph_id="verify_group",
        project_id="EXAMPLE-SOC",
        stage="simulation",
        group="gpio_ext",
    )
    from soc_verify.graph_session import session_status

    st = session_status(ROOT, started["session_id"])
    assert st.get("node_contract", "").endswith("node_contract.yaml")
    assert "node_sandbox" in st or st.get("current_node") == "load_context"


def test_session_sandbox_capabilities():
    started = start_session(
        ROOT,
        graph_id="verify_group",
        project_id="EXAMPLE-SOC",
        stage="simulation",
        group="gpio_ext",
    )
    sid = started["session_id"]
    session_tick(ROOT, sid)
    cap = session_sandbox(ROOT, sid, action="capabilities")
    assert cap.get("ok") is True
    sandbox = cap.get("sandbox") or {}
    assert sandbox.get("node") in ("load_context", "select_runner", "setup")