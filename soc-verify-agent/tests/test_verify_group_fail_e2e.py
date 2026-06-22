"""verify_group FAIL path — validation items + triage routing."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from soc_verify.graph_session import session_status, session_tick, start_session
from soc_verify.graphs.verify_routing import route_after_run
from soc_verify.models import Verdict
from soc_verify.node_triage import resolve_route

ROOT = Path(__file__).resolve().parents[1]
MAX_TICKS = 25


def test_fail_verification_routes_to_parse_validation_items():
    state = {
        "verdict": "FAIL",
        "error_kind": "verification",
        "project_dir": str(ROOT / "projects" / "EXAMPLE-SOC"),
        "run_id": "x",
    }
    assert route_after_run(state) == "parse_validation_items"


def test_oscillation_stalemate_routes_to_validation(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    state = {
        "project_dir": str(tmp_path),
        "run_id": "run",
        "verdict": "FAIL",
        "error_kind": "verification",
        "stalemate": True,
        "stalemate_pattern": "OSCILLATION",
    }
    route = resolve_route(ROOT, "verify_group", "run_gate", state, run_dir=run_dir)
    assert route == "parse_validation_items"


@patch("soc_verify.graphs.verify_group.select_runner", return_value="python")
@patch("soc_verify.graphs.verify_group.run_python_script")
def test_verify_group_fail_path_reaches_validation_nodes(mock_run, _mock_runner):
    def _fail_run(script_path, *, project_dir, run_dir, gate):
        verdict = Verdict(
            gate=gate,
            status="FAIL",
            exit_code=1,
            evidence=["tier T1 FAIL"],
        )
        (run_dir / f"verdict_{gate}.json").write_text(
            __import__("json").dumps(verdict.to_dict(), indent=2),
            encoding="utf-8",
        )
        return verdict

    mock_run.side_effect = _fail_run

    started = start_session(
        ROOT,
        graph_id="verify_group",
        project_id="EXAMPLE-SOC",
        stage="simulation",
        group="gpio_ext",
    )
    sid = started["session_id"]
    seen: list[str] = []

    for _ in range(MAX_TICKS):
        last = session_tick(ROOT, sid, auto_invoke_llm=False)
        if last.get("tick") == "blocked":
            pytest.fail(
                f"blocked: {last.get('blocked_reason')} contract={last.get('contract')}"
            )
        completed = last.get("completed_node")
        if completed:
            seen.append(completed)
        if session_status(ROOT, sid).get("finished"):
            break

    assert "run_gate" in seen
    assert "parse_validation_items" in seen
    assert "validation_judge" in seen
    assert "apply_validation_plan" in seen