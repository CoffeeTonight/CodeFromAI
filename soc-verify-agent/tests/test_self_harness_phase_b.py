"""Unit tests for VERIF-CPU-SOC self-harness Phase B (LLM patches, held-out, meta_collect)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_DIR = Path(__file__).resolve().parents[1] / "projects" / "VERIF-CPU-SOC"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from ops.llm_brief import build_llm_brief, inject_erl_into_llm_brief, setup_group_injection  # noqa: E402
from ops.meta_collect import build_meta_collect_payload, run_meta_collect, write_meta_collect_prompt  # noqa: E402
from ops.self_harness import (  # noqa: E402
    held_out_reverify,
    propose_harness_edits,
    propose_llm_skill_patches,
    validate_harness_proposal,
    write_weakness_report,
)


def _signals(**overrides) -> dict:
    base = {
        "run_id": "sh-b-run",
        "project_id": "VERIF-CPU-SOC",
        "stage": "simulation",
        "group": "gpio_ext",
        "verdict": "FAIL",
        "error_kind": "verification",
        "parity_ok": False,
    }
    base.update(overrides)
    return base


@pytest.fixture()
def run_tree(tmp_path: Path):
    project_dir = tmp_path / "VERIF-CPU-SOC"
    run_dir = project_dir / "runs" / "sh-b-run"
    run_dir.mkdir(parents=True)
    (tmp_path / "registry").mkdir()
    spec_src = ROOT / "registry" / "self_harness_spec.yaml"
    if spec_src.is_file():
        (tmp_path / "registry" / "self_harness_spec.yaml").write_text(
            spec_src.read_text(encoding="utf-8"), encoding="utf-8"
        )
    (run_dir / "improvement_signal.json").write_text(json.dumps(_signals()), encoding="utf-8")
    (run_dir / "improvement_snapshot.json").write_text(
        json.dumps({"stage": "simulation", "group": "gpio_ext", "improvement_index": 1}),
        encoding="utf-8",
    )
    (run_dir / "sub_stop.json").write_text(
        json.dumps({"reason": "gate script error"}), encoding="utf-8"
    )
    return tmp_path, project_dir, run_dir


def test_propose_llm_skill_patches_structure(run_tree):
    root, project_dir, run_dir = run_tree
    report = {
        "stage": "simulation",
        "group": "gpio_ext",
        "weaknesses": [
            {"category": "tool_artifact", "summary": "bad artifact"},
            {"category": "parity_block", "summary": "parity mismatch"},
        ],
    }
    write_weakness_report(run_dir, report)
    payload = propose_llm_skill_patches(root, project_dir, run_dir)
    assert payload["contract"] == "harness_proposal_llm_v1"
    assert len(payload["patches"]) == 2
    assert payload["patches"][0]["patch_type"] == "append_section"
    assert payload["patches"][0]["auto_apply"] is False
    assert (run_dir / "harness_proposal_llm.json").is_file()


def test_validate_harness_proposal_mock(run_tree):
    root, project_dir, run_dir = run_tree
    write_weakness_report(
        run_dir,
        {"weaknesses": [{"category": "tool_artifact", "summary": "x"}]},
    )
    propose_harness_edits(root, project_dir, run_dir)

    class FakeProc:
        returncode = 0
        stdout = "5 passed"
        stderr = ""

    with patch("ops.self_harness.subprocess.run", return_value=FakeProc()):
        result = validate_harness_proposal(root, run_dir)
    assert result["ok"] is True
    assert (run_dir / "harness_validation.json").is_file()


def test_held_out_reverify_mock(run_tree):
    root, _, run_dir = run_tree

    class FakeProc:
        returncode = 0
        stdout = "10 passed"
        stderr = ""

    with patch("ops.self_harness.subprocess.run", return_value=FakeProc()):
        result = held_out_reverify(root, run_dir)
    assert result["ok"] is True
    assert result["promote_allowed"] is True
    assert (run_dir / "harness_held_out_validation.json").is_file()


def test_llm_brief_erl_injection(run_tree):
    _, project_dir, run_dir = run_tree
    patterns = project_dir / "knowledge" / "patterns"
    patterns.mkdir(parents=True)
    (patterns / "prior.md").write_text(
        "tags: #project/VERIF-CPU-SOC #stage/simulation #group/gpio_ext #error_kind/verification\n\n## Try\nretry\n",
        encoding="utf-8",
    )
    brief = build_llm_brief(project_dir, run_dir, stage="simulation", group="gpio_ext")
    assert brief["contract"] == "llm_brief_v1"
    injected = inject_erl_into_llm_brief(
        brief, project_dir, stage="simulation", group="gpio_ext", error_kind="verification"
    )
    assert injected["erl_context"]["count"] >= 1
    assert "erl_context" in setup_group_injection(project_dir, run_dir)
    assert (run_dir / "llm_brief.json").is_file()


def test_run_meta_collect_pipeline(run_tree):
    root, project_dir, run_dir = run_tree
    (run_dir / "verdict_gpio_ext.json").write_text(
        json.dumps({"verdict": "FAIL", "summary": "tier markers missing"}),
        encoding="utf-8",
    )
    result = run_meta_collect(root, project_dir, run_dir)
    assert result["ok"] is True
    assert result["weakness_count"] >= 1
    assert result["proposal_count"] >= 1
    assert result["llm_patch_count"] >= 1
    assert result["llm_brief_written"] is True
    assert (run_dir / "meta_collect_prompt.json").is_file()
    payload = json.loads((run_dir / "meta_collect_prompt.json").read_text(encoding="utf-8"))
    assert payload["contract"] == "meta_collect_v1"
    assert payload["self_harness"] is True
    assert "weakness_report" in payload