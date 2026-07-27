"""MINI-SOC graph routing for env_fail and verif_fail scenarios."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from soc_verify.graph_session import session_status, session_tick, start_session
from soc_verify.loop_lap import set_training_scenario
from tests.e2e_fixture import reset_mini_soc_e2e_trust

ROOT = Path(__file__).resolve().parents[1]
MINI = ROOT / "projects" / "MINI-SOC"
MAX_TICKS = 20


@pytest.fixture(autouse=True)
def _reset_mini_soc_fixture():
    reset_mini_soc_e2e_trust()
    set_training_scenario(MINI, "pass")
    yield
    reset_mini_soc_e2e_trust()
    set_training_scenario(MINI, "pass")


def _ticks_until_nodes(project_id: str, scenario: str, want: set[str]) -> list[str]:
    set_training_scenario(ROOT / "projects" / project_id, scenario)
    started = start_session(
        ROOT,
        graph_id="verify_group",
        project_id=project_id,
        stage="simulation",
        group="mini_gate",
        run_profile="training",
    )
    sid = started["session_id"]
    seen: list[str] = []

    llm_exit_nodes = {"diagnose_env", "validation_judge", "promote", "finalize_reproduction"}

    for _ in range(MAX_TICKS):
        last = session_tick(ROOT, sid, auto_invoke_llm=False)
        if last.get("tick") == "blocked":
            contract = last.get("contract") or {}
            node = str(contract.get("recovery_node") or contract.get("node") or "")
            if node in llm_exit_nodes:
                seen.append(node)
                if want.issubset(set(seen)):
                    return seen
            pytest.fail(f"blocked: {last.get('blocked_reason')} contract={last.get('contract')}")
        completed = last.get("completed_node")
        if completed:
            seen.append(completed)
        if want.issubset(set(seen)):
            return seen
        if session_status(ROOT, sid).get("finished"):
            break
    return seen


@patch("soc_verify.graphs.verify_group.select_runner", return_value="python")
def test_mini_soc_verif_fail_reaches_validation(_mock_runner):
    seen = _ticks_until_nodes("MINI-SOC", "verif_fail", {"parse_validation_items"})
    assert "run_gate" in seen
    assert "parse_validation_items" in seen


@patch("soc_verify.graphs.verify_group.select_runner", return_value="python")
def test_mini_soc_env_fail_reaches_diagnose_env(_mock_runner):
    seen = _ticks_until_nodes("MINI-SOC", "env_fail", {"diagnose_env"})
    assert "run_gate" in seen
    assert "diagnose_env" in seen