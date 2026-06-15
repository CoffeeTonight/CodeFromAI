from __future__ import annotations

import json
import uuid
from pathlib import Path

from soc_verify.bridge_env import (
    apply_bridge_patch,
    apply_profile_to_environ,
    bridge_script_path,
    classify_gate_failure,
    extract_python_from_proposal,
)
from soc_verify.constants import EXIT_TOOL_ERROR
from soc_verify.graphs.verify_group import route_after_run
from soc_verify.models import Verdict


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "projects" / "EXAMPLE-SOC"


def test_classify_verification_vs_tool():
    v_ver = Verdict(gate="g", status="FAIL", exit_code=1, metrics={"failure_kind": "verification"})
    assert classify_gate_failure(verdict=v_ver) == "verification"

    v_tool = Verdict(gate="g", status="FAIL", exit_code=EXIT_TOOL_ERROR)
    assert classify_gate_failure(verdict=v_tool) == "tool"

    v_env = Verdict(gate="g", status="FAIL", exit_code=1, metrics={"failure_kind": "env"})
    assert classify_gate_failure(verdict=v_env) == "env"


def test_route_after_run_env_goes_diagnose():
    assert route_after_run({"verdict": "FAIL", "error_kind": "env"}) == "diagnose_env"
    assert route_after_run({"verdict": "FAIL", "error_kind": "tool"}) == "diagnose_env"


def test_route_after_run_verification_retries_runner():
    assert route_after_run({"verdict": "FAIL", "error_kind": "verification"}) == "select_runner"


def test_route_after_run_pass_evaluates():
    assert route_after_run({"verdict": "PASS", "error_kind": "none"}) == "evaluate"


def test_extract_and_apply_bridge_patch(tmp_path: Path):
    project = tmp_path / "proj"
    project.mkdir()
    run_dir = project / "runs" / "r1"
    run_dir.mkdir(parents=True)
    proposal = '## patch\n```python\ndef setup_env():\n    pass\n```\n'
    (run_dir / "bridge_patch_proposal.md").write_text(proposal, encoding="utf-8")

    code = extract_python_from_proposal(proposal)
    assert code and "setup_env" in code

    out = apply_bridge_patch(project, "simulation", "gpio_ext", run_dir, force=True)
    assert out["applied"] is True
    assert bridge_script_path(project, "simulation", "gpio_ext").is_file()


def test_apply_profile_to_environ(tmp_path: Path):
    project = tmp_path / "proj"
    (project / "meta").mkdir(parents=True)
    (project / "meta" / "environment_profile.yaml").write_text(
        "env:\n  FOO: bar\n",
        encoding="utf-8",
    )
    env = apply_profile_to_environ(project, base={})
    assert env.get("FOO") == "bar"


def test_graph_flow_spec_has_bridge_nodes():
    from soc_verify.graph_spec import load_flow_spec

    spec = load_flow_spec(ROOT)
    nodes = (spec.get("graphs") or {}).get("verify_group", {}).get("nodes") or {}
    assert "diagnose_env" in nodes
    assert "patch_bridge" in nodes
    edges = (spec.get("graphs") or {}).get("verify_group", {}).get("edges") or {}
    assert "diagnose_env" in edges.get("run_gate", [])