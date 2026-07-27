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
    load_env_diagnosis,
)
from soc_verify.models import load_yaml
from soc_verify.constants import EXIT_TOOL_ERROR
from soc_verify.graphs.verify_group import route_after_run
from soc_verify.models import Verdict


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "projects" / "EXAMPLE-SOC"


def test_classify_pass_is_none():
    v_pass = Verdict(gate="g", status="PASS", exit_code=0)
    assert classify_gate_failure(verdict=v_pass) == "none"


def test_classify_blocked_is_env():
    from soc_verify.constants import EXIT_BLOCKED

    v_blocked = Verdict(gate="g", status="BLOCKED", exit_code=EXIT_BLOCKED)
    assert classify_gate_failure(verdict=v_blocked) == "env"


def test_classify_info_metrics():
    v_info = Verdict(
        gate="g",
        status="FAIL",
        exit_code=1,
        metrics={"failure_kind": "info"},
    )
    assert classify_gate_failure(verdict=v_info) == "info"


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


def test_route_after_run_verification_goes_validation_autonomy():
    assert route_after_run({"verdict": "FAIL", "error_kind": "verification"}) == "parse_validation_items"


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


def test_load_env_diagnosis_parses_markdown_profile_patch(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "r1"
    run_dir.mkdir(parents=True)
    (run_dir / "env_diagnosis.md").write_text(
        "## environment_profile_patch\n```json\n"
        '{"env": {"TOOL": "vcs"}, "toolchain": "synopsys", "notes": "patched"}\n'
        "```\n",
        encoding="utf-8",
    )
    diagnosis = load_env_diagnosis(run_dir)
    assert diagnosis.get("environment_profile_patch", {}).get("env", {}).get("TOOL") == "vcs"


def test_apply_bridge_patch_profile_only_without_python(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    (project / "meta").mkdir(parents=True)
    (project / "meta" / "environment_profile.yaml").write_text("env: {}\n", encoding="utf-8")
    run_dir = project / "runs" / "r1"
    run_dir.mkdir(parents=True)
    (run_dir / "env_diagnosis.md").write_text(
        "```json\n{\"env\": {\"ONLY_PROFILE\": \"yes\"}}\n```\n",
        encoding="utf-8",
    )
    out = apply_bridge_patch(project, "simulation", "gpio_ext", run_dir, force=True)
    assert out["applied"] is True
    assert out.get("reason") == "profile_only"
    profile = load_yaml(project / "meta" / "environment_profile.yaml")
    assert profile.get("env", {}).get("ONLY_PROFILE") == "yes"


def test_apply_bridge_patch_applies_markdown_profile_patch(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    (project / "meta").mkdir(parents=True)
    (project / "meta" / "environment_profile.yaml").write_text("env: {}\n", encoding="utf-8")
    run_dir = project / "runs" / "r1"
    run_dir.mkdir(parents=True)
    (run_dir / "bridge_patch_proposal.md").write_text(
        "```python\ndef setup_env():\n    pass\n```\n",
        encoding="utf-8",
    )
    (run_dir / "env_diagnosis.md").write_text(
        "```json\n{\"env\": {\"PATCHED\": \"yes\"}}\n```\n",
        encoding="utf-8",
    )
    out = apply_bridge_patch(project, "simulation", "gpio_ext", run_dir, force=True)
    assert out["applied"] is True
    profile = load_yaml(project / "meta" / "environment_profile.yaml")
    assert profile.get("env", {}).get("PATCHED") == "yes"


def test_apply_profile_to_environ(tmp_path: Path):
    project = tmp_path / "proj"
    (project / "meta").mkdir(parents=True)
    (project / "meta" / "environment_profile.yaml").write_text(
        "env:\n  FOO: bar\n",
        encoding="utf-8",
    )
    env = apply_profile_to_environ(project, base={})
    assert env.get("FOO") == "bar"


def test_apply_profile_to_environ_skips_non_dict_env(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    (project / "meta").mkdir(parents=True)
    (project / "meta" / "environment_profile.yaml").write_text(
        "env: not-a-dict\n",
        encoding="utf-8",
    )
    env = apply_profile_to_environ(project, base={"KEEP": "yes"})
    assert env.get("KEEP") == "yes"
    assert "FOO" not in env


def test_graph_flow_spec_has_bridge_nodes():
    from soc_verify.graph_spec import load_flow_spec

    spec = load_flow_spec(ROOT)
    nodes = (spec.get("graphs") or {}).get("verify_group", {}).get("nodes") or {}
    assert "diagnose_env" in nodes
    assert "patch_bridge" in nodes
    edges = (spec.get("graphs") or {}).get("verify_group", {}).get("edges") or {}
    assert "diagnose_env" in edges.get("run_gate", [])