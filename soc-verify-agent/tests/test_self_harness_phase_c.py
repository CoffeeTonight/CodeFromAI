"""Phase C — meta_collect graph wiring, LLM prompt, held-out intake replay."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT / "projects" / "VERIF-CPU-SOC"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(PROJECT_DIR))

from soc_verify.self_harness import (  # noqa: E402
    integrate_meta_collect,
    merge_meta_collect_payloads,
)
from ops.self_harness import (  # noqa: E402
    held_out_intake_replay,
    write_harness_llm_prompt,
)


def _signals(**overrides) -> dict:
    base = {
        "run_id": "sh-c-run",
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
    run_dir = project_dir / "runs" / "sh-c-run"
    run_dir.mkdir(parents=True)
    (tmp_path / "registry").mkdir()
    spec_src = ROOT / "registry" / "self_harness_spec.yaml"
    if spec_src.is_file():
        (tmp_path / "registry" / "self_harness_spec.yaml").write_text(
            spec_src.read_text(encoding="utf-8"), encoding="utf-8"
        )
    intake_dir = project_dir / "inputs/tags/main/deployment"
    intake_dir.mkdir(parents=True)
    (intake_dir / "customer_soc_intake.example.yaml").write_text(
        "integration_tier: tier1\nsimulation:\n  enabled: true\n",
        encoding="utf-8",
    )
    (run_dir / "improvement_signal.json").write_text(json.dumps(_signals()), encoding="utf-8")
    (run_dir / "improvement_snapshot.json").write_text(
        json.dumps({"stage": "simulation", "group": "gpio_ext", "improvement_index": 1}),
        encoding="utf-8",
    )
    (run_dir / "sub_stop.json").write_text(json.dumps({"reason": "gate error"}), encoding="utf-8")
    (run_dir / "verdict_gpio_ext.json").write_text(
        json.dumps({"verdict": "FAIL", "summary": "tier markers missing"}),
        encoding="utf-8",
    )
    return tmp_path, project_dir, run_dir


def test_merge_meta_collect_payloads_preserves_change_hints():
    meta = {
        "contract": "meta_collect_v1",
        "change_hints": [{"layer": "ops", "reason": "parity_fail"}],
        "instruction": "meta instruction",
    }
    harness = {
        "self_harness": True,
        "weakness_report": {"weaknesses": [{"category": "tool_artifact"}]},
        "self_harness_hints": [{"category": "tool_artifact"}],
        "instruction": "self-harness instruction",
    }
    merged = merge_meta_collect_payloads(meta, harness)
    assert merged["change_hints"] == meta["change_hints"]
    assert merged["self_harness"] is True
    assert "weakness_report" in merged
    assert "self-harness instruction" in merged["instruction"]


def test_integrate_meta_collect_writes_artifacts(run_tree):
    root, project_dir, run_dir = run_tree
    signals = _signals()
    snapshot = {"stage": "simulation", "group": "gpio_ext", "improvement_index": 1}
    meta_payload = {
        "contract": "meta_collect_v1",
        "change_hints": [],
        "instruction": "meta_graph instruction",
    }
    result = integrate_meta_collect(
        root,
        project_dir,
        run_dir,
        meta_payload=meta_payload,
        signals=signals,
        snapshot=snapshot,
    )
    assert result["ok"] is True
    assert result["weakness_count"] >= 1
    assert result["harness_llm_prompt_written"] is True
    assert (run_dir / "weakness_report.json").is_file()
    assert (run_dir / "harness_llm_prompt.json").is_file()
    assert (run_dir / "llm_brief.json").is_file()
    payload = result["payload"]
    assert payload["self_harness"] is True
    assert payload["change_hints"] == []


def test_write_harness_llm_prompt_structure(run_tree):
    root, project_dir, run_dir = run_tree
    report = {
        "stage": "simulation",
        "group": "gpio_ext",
        "weaknesses": [{"category": "tool_artifact", "summary": "bad artifact"}],
    }
    payload = write_harness_llm_prompt(root, project_dir, run_dir, weakness_report=report)
    assert payload["contract"] == "harness_llm_prompt_v1"
    assert len(payload["weaknesses"]) == 1
    assert (run_dir / "harness_llm_prompt.json").is_file()


def test_held_out_intake_replay_on_example_yaml(run_tree):
    root, project_dir, _ = run_tree
    result = held_out_intake_replay(root, project_dir)
    assert "intake_path" in result
    assert result["intake_path"].endswith("customer_soc_intake.example.yaml")


def test_meta_collect_node_wiring_smoke(run_tree):
    """Smoke: integrate_meta_collect produces merged payload like verify_group meta_collect_node."""
    root, project_dir, run_dir = run_tree
    from soc_verify.meta_graph import build_meta_collect_payload

    signals = _signals()
    snapshot = {"stage": "simulation", "group": "gpio_ext", "improvement_index": 2}
    meta_payload = build_meta_collect_payload(
        root=root,
        project_dir=project_dir,
        run_dir=run_dir,
        signals=signals,
        snapshot=snapshot,
        state={},
    )
    result = integrate_meta_collect(
        root,
        project_dir,
        run_dir,
        meta_payload=meta_payload,
        signals=signals,
        snapshot=snapshot,
    )
    merged = result["payload"]
    assert merged.get("change_hints") is not None or "trend" in merged or "improvement_signal" in merged
    assert merged["self_harness"] is True
    assert "weakness_report" in merged


def test_held_out_reverify_with_intake_mock(run_tree):
    root, project_dir, run_dir = run_tree

    class FakeProc:
        returncode = 0
        stdout = "ok"
        stderr = ""

    with patch("ops.self_harness.subprocess.run", return_value=FakeProc()):
        from ops.self_harness import held_out_reverify

        result = held_out_reverify(root, run_dir, project_dir=project_dir)
    assert "intake_replay" in result
    assert result["pytest_passed"] is True