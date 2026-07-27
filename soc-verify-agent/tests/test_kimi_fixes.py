"""Regression tests for Kimi code-review findings."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from soc_verify.bridge_env import apply_bridge_patch
from soc_verify.completeness import CompletenessMetrics
from soc_verify.error_classify import (
    bump_events,
    classify_exit_code,
    classify_stop_report,
    resolve_bump_kind,
)
from soc_verify.constants import EXIT_BLOCKED, EXIT_FAIL, EXIT_INFO_GAP, EXIT_TOOL_ERROR
from soc_verify.graph_checkpointer import get_graph_checkpointer, reset_graph_checkpointer_cache
from soc_verify.graph_session import session_status, session_tick, start_session
from soc_verify.graphs.verify_group import load_context, run_gate, run_codegen_node
from soc_verify.models import Verdict
from soc_verify.runner import run_python_script
from soc_verify.llm_runner import extract_verdict_dict_from_text
from soc_verify.models import save_yaml
from soc_verify.trust_eval import select_runner


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "projects" / "EXAMPLE-SOC"


def test_classify_exit_code_fail_is_verification_not_env():
    assert classify_exit_code(EXIT_FAIL) == "verification"
    assert classify_exit_code(EXIT_BLOCKED) == "env"
    assert classify_exit_code(EXIT_INFO_GAP) == "info"
    assert classify_exit_code(EXIT_TOOL_ERROR) == "tool"


def test_resolve_bump_kind_verification_fail():
    assert resolve_bump_kind("verification", exit_code=EXIT_FAIL) == "verification"
    assert resolve_bump_kind("none", exit_code=EXIT_FAIL) == "verification"


@pytest.mark.parametrize(
    "report,expected",
    [
        ({"error_code": "3"}, "tool"),
        ({"error_code": "EXIT_BLOCKED"}, "env"),
        ({"stop_reason": "verification pathway mismatch"}, "verification"),
        ({"stop_reason": "missing license file"}, "env"),
        ({"stop_reason": "information only"}, "verification"),
        ({"stop_reason": "no info provided"}, "verification"),
        ({"stop_reason": "coverage gap vs spec"}, "verification"),
        ({"partial_verdict": "INFO_GAP"}, "info"),
    ],
)
def test_classify_stop_report_structured(report: dict, expected: str) -> None:
    assert classify_stop_report(report) == expected


def test_bump_events_increments_fix_rounds():
    events = bump_events({"llm_fix_rounds": 1, "fix_rounds": 2}, "verification")
    assert events["fix_rounds"] == 3
    assert events["verification_fail_steps"] == 1
    assert events["llm_fix_rounds"] == 1

    events = bump_events(events, "llm")
    assert events["fix_rounds"] == 4
    assert events["llm_fix_rounds"] == 2


def test_completeness_l_uses_distinct_fix_rounds():
    m = CompletenessMetrics.from_events(
        {"gates_run": 5, "llm_fix_rounds": 2, "fix_rounds": 5}
    )
    assert m.l == pytest.approx(2 / 6)


def test_select_runner_canonical_bypasses_low_completeness(tmp_path: Path):
    project = tmp_path / "P1"
    trust_dir = project / "trust"
    trust_dir.mkdir(parents=True)
    save_yaml(
        trust_dir / "registry.yaml",
        {
            "scripts": {
                "gpio_ext.py": {
                    "script": "gpio_ext.py",
                    "status": "canonical",
                    "trust_score": 0.9,
                }
            }
        },
    )
    assert (
        select_runner(project, "gpio_ext.py", 0.75, completeness=0.2, tau_completeness=0.75)
        == "python"
    )
    assert (
        select_runner(project, "other.py", 0.9, completeness=0.2, tau_completeness=0.75)
        == "llm"
    )


def test_extract_verdict_rejects_bare_pass_keyword():
    assert extract_verdict_dict_from_text('Looks good — PASS') is None
    assert extract_verdict_dict_from_text('{"status":"PASS"}') is None
    ok = extract_verdict_dict_from_text(
        json.dumps({"gate": "gpio_ext", "status": "PASS", "exit_code": 0, "evidence": ["x"]})
    )
    assert ok is not None
    assert ok["status"] == "PASS"


def test_apply_bridge_patch_creates_backup(tmp_path: Path):
    project = tmp_path / "SOC"
    stage, group = "simulation", "gpio_ext"
    bridge = project / "bridge" / stage / f"{group}.py"
    bridge.parent.mkdir(parents=True)
    bridge.write_text("# original\n", encoding="utf-8")
    run_dir = project / "runs" / "run001"
    run_dir.mkdir(parents=True)
    (run_dir / "bridge_patch_proposal.md").write_text(
        "```python\nprint('patched')\n```\n",
        encoding="utf-8",
    )
    out = apply_bridge_patch(project, stage, group, run_dir, force=True)
    assert out["applied"] is True
    backup = Path(out["backup_path"])
    assert backup.is_file()
    assert "# original" in backup.read_text(encoding="utf-8")
    assert "patched" in bridge.read_text(encoding="utf-8")


def test_fresh_project_load_context_info_gap(tmp_path: Path):
    project = tmp_path / "EMPTY-SOC"
    project.mkdir()
    for name in ("discovered.yaml", "state.yaml", "cache.yaml", "meta.yaml"):
        (project / name).write_text("{}\n", encoding="utf-8")

    run_dir = project / "runs" / "gap001"
    run_dir.mkdir(parents=True)
    state = {
        "project_dir": str(project),
        "stage": "simulation",
        "group": "gpio_ext",
        "run_id": "gap001",
    }
    out = load_context(state)
    assert out.get("info_gap") is True
    assert out.get("verdict") == "INFO_GAP"


def test_graph_session_resume_survives_process_restart(tmp_path: Path):
    """Sqlite checkpointer: state survives in-process cache reset."""
    root = tmp_path / "workspace"
    root.mkdir()
    shutil.copytree(ROOT / "registry", root / "registry")
    shutil.copytree(ROOT / "templates", root / "templates")
    (root / "config.json").write_text(
        json.dumps(
            {
                "llm": {"mode": "stub"},
                "schedules": {},
            }
        ),
        encoding="utf-8",
    )
    project = root / "projects" / "EXAMPLE-SOC"
    shutil.copytree(EXAMPLE, project)

    started = start_session(
        root,
        graph_id="verify_group",
        project_id="EXAMPLE-SOC",
        stage="simulation",
        group="gpio_ext",
    )
    session_id = started["session_id"]
    session_tick(root, session_id)

    st_before = session_status(root, session_id)
    assert st_before.get("started") or st_before.get("state")

    reset_graph_checkpointer_cache()
    get_graph_checkpointer(root)

    st_after = session_status(root, session_id)
    assert st_after["session_id"] == session_id
    assert st_after.get("state") or st_after.get("last_completed_node")


def test_run_codegen_allows_exactly_max_rounds(tmp_path: Path, monkeypatch):
    """max_codegen_rounds=N must allow exactly N codegen attempts (cap on N+1)."""
    run_dir = tmp_path / "runs" / "r1"
    run_dir.mkdir(parents=True)
    project_dir = EXAMPLE
    state = {
        "project_dir": str(project_dir),
        "run_id": "r1",
        "stage": "simulation",
        "group": "gpio_ext",
        "codegen_round": 10,
        "group_context": {},
    }
    monkeypatch.setattr(
        "soc_verify.graphs.verify_group._run_dir",
        lambda _state: run_dir,
    )
    monkeypatch.setattr("soc_verify.graphs.verify_group.invoke_sub_agent", lambda *_a, **_k: None)

    out_at_max = run_codegen_node(state)
    assert out_at_max.get("error") != "codegen_round_cap"
    assert out_at_max.get("codegen_round") == 10

    state["codegen_round"] = 11
    out_over = run_codegen_node(state)
    assert out_over.get("error") == "codegen_round_cap"


def test_run_gate_python_info_gap_sets_info_gap_fields(monkeypatch, tmp_path: Path) -> None:
    project = tmp_path / "projects" / "P1"
    run_dir = project / "runs" / "r1"
    run_dir.mkdir(parents=True)
    script = project / "ops" / "simulation" / "gpio_ext.py"
    script.parent.mkdir(parents=True)
    script.write_text("# stub\n", encoding="utf-8")
    shutil.copytree(ROOT / "registry", tmp_path / "registry", dirs_exist_ok=True)

    def _fake_run(*_a, **_k):
        return Verdict(
            gate="gpio_ext",
            status="INFO_GAP",
            exit_code=EXIT_INFO_GAP,
            evidence=["need PLL config"],
        )

    monkeypatch.setattr("soc_verify.graphs.verify_group.run_python_script", _fake_run)
    monkeypatch.setattr(
        "soc_verify.graphs.verify_group._project_dir",
        lambda _s: project,
    )
    monkeypatch.setattr(
        "soc_verify.graphs.verify_group._run_dir",
        lambda _s: run_dir,
    )
    state = {
        "project_dir": str(project),
        "run_id": "r1",
        "stage": "simulation",
        "group": "gpio_ext",
        "runner": "python",
        "events": {},
        "fix_round": 0,
        "orchestrator_run_id": "",
    }
    out = run_gate(state)
    assert out.get("info_gap") is True
    assert "PLL" in str(out.get("info_gap_message", ""))
    assert out.get("verdict") == "INFO_GAP"
    assert out.get("error_kind") == "info"


def test_run_python_script_corrupt_verdict_falls_back(monkeypatch, tmp_path: Path) -> None:
    from unittest.mock import MagicMock

    import subprocess

    project = tmp_path / "proj"
    run_dir = tmp_path / "run"
    project.mkdir()
    run_dir.mkdir()
    script = project / "ops.py"
    script.write_text("pass\n", encoding="utf-8")
    (run_dir / "verdict_gpio_ext.json").write_text("{not valid json", encoding="utf-8")

    mock_proc = MagicMock()
    mock_proc.returncode = EXIT_FAIL
    mock_proc.stdout = ""
    mock_proc.stderr = "gate failed"
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: mock_proc)

    verdict = run_python_script(
        script, project_dir=project, run_dir=run_dir, gate="gpio_ext"
    )
    assert verdict.status == "FAIL"
    assert verdict.exit_code == EXIT_FAIL