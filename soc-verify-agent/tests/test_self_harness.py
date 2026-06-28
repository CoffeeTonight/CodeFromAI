"""Unit tests for VERIF-CPU-SOC self-harness ops (no full soc_verify package)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parents[1] / "projects" / "VERIF-CPU-SOC"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from ops.erl_reflect import build_heuristic_markdown, write_erl_heuristic  # noqa: E402
from ops.self_harness import (  # noqa: E402
    harness_status,
    load_weakness_report,
    mine_weaknesses,
    propose_harness_edits,
    retrieve_erl_context,
    update_patterns_index,
    write_weakness_report,
)


def _signals(**overrides) -> dict:
    base = {
        "run_id": "run-test",
        "project_id": "VERIF-CPU-SOC",
        "stage": "simulation",
        "group": "gpio_ext",
        "verdict": "FAIL",
        "error_kind": "verification",
        "env_fail_steps": 0,
        "stalemate": False,
        "parity_ok": True,
        "llm_fix_rounds": 0,
        "promoted": True,
    }
    base.update(overrides)
    return base


@pytest.fixture()
def run_tree(tmp_path: Path):
    project_dir = tmp_path / "VERIF-CPU-SOC"
    run_dir = project_dir / "runs" / "sh-run-1"
    run_dir.mkdir(parents=True)
    (tmp_path / "registry").mkdir()
    spec_src = ROOT / "registry" / "self_harness_spec.yaml"
    if spec_src.is_file():
        (tmp_path / "registry" / "self_harness_spec.yaml").write_text(
            spec_src.read_text(encoding="utf-8"), encoding="utf-8"
        )
    return tmp_path, project_dir, run_dir


def test_mine_weaknesses_from_sub_stop_and_env(run_tree):
    root, project_dir, run_dir = run_tree
    (run_dir / "sub_stop.json").write_text(
        json.dumps({"reason": "syntax error in gate script"}), encoding="utf-8"
    )
    (run_dir / "improvement_signal.json").write_text(
        json.dumps(_signals(env_fail_steps=3, stalemate=True, stalemate_pattern="OSCILLATION")),
        encoding="utf-8",
    )
    report = mine_weaknesses(root, project_dir, run_dir)
    cats = {w["category"] for w in report["weaknesses"]}
    assert "tool_artifact" in cats
    assert "env_loop" in cats
    assert "stalemate_oscillation" in cats
    write_weakness_report(run_dir, report)
    assert load_weakness_report(run_dir)["contract"] == "weakness_report_v1"


def test_propose_harness_edits_layers(run_tree):
    root, project_dir, run_dir = run_tree
    report = {
        "stage": "simulation",
        "group": "gpio_ext",
        "weaknesses": [
            {"category": "tool_artifact", "summary": "bad artifact"},
            {"category": "parity_block", "summary": "parity"},
        ],
    }
    write_weakness_report(run_dir, report)
    payload = propose_harness_edits(root, project_dir, run_dir)
    layers = {p["layer"] for p in payload["proposals"]}
    assert "skill" in layers
    assert "graph_source" in layers
    assert all(p["approval"] for p in payload["proposals"])


def test_erl_skips_clean_pass(run_tree):
    _, project_dir, run_dir = run_tree
    (run_dir / "improvement_signal.json").write_text(
        json.dumps(_signals(verdict="PASS")), encoding="utf-8"
    )
    path = write_erl_heuristic(project_dir, run_dir, signals=_signals(verdict="PASS"))
    assert path is None


def test_erl_writes_on_fail(run_tree):
    _, project_dir, run_dir = run_tree
    write_weakness_report(
        run_dir,
        {"weaknesses": [{"category": "info_gap", "summary": "missing paths"}]},
    )
    path = write_erl_heuristic(
        project_dir,
        run_dir,
        signals=_signals(verdict="FAIL", error_kind="info"),
        weakness_report=load_weakness_report(run_dir),
    )
    assert path is not None and path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "## When" in text and "## Try" in text and "## Avoid" in text


def test_retrieve_erl_context_ranking(run_tree):
    _, project_dir, _ = run_tree
    patterns = project_dir / "knowledge" / "patterns"
    patterns.mkdir(parents=True)
    (patterns / "old.md").write_text(
        "tags: #project/VERIF-CPU-SOC #stage/unit #group/other\n\nbody\n",
        encoding="utf-8",
    )
    (patterns / "new.md").write_text(
        "tags: #project/VERIF-CPU-SOC #stage/simulation #group/gpio_ext #error_kind/verification\n\nbody\n",
        encoding="utf-8",
    )
    ctx = retrieve_erl_context(
        project_dir, stage="simulation", group="gpio_ext", error_kind="verification", limit=2
    )
    assert ctx[0]["run_id"] == "new"
    assert ctx[0]["score"] >= ctx[1]["score"]


def test_harness_status_flags(run_tree):
    _, project_dir, run_dir = run_tree
    write_weakness_report(run_dir, {"weaknesses": []})
    propose_harness_edits(run_tree[0], project_dir, run_dir)
    status = harness_status(project_dir, run_dir)
    assert status["artifacts"]["weakness_report"] is True
    assert status["artifacts"]["harness_proposal"] is True


def test_build_heuristic_markdown_structure():
    body, tags = build_heuristic_markdown(
        project_id="P",
        run_id="r1",
        stage="sim",
        group="g",
        signals={"verdict": "FAIL", "error_kind": "env"},
        weakness_report={"weaknesses": [{"category": "env_loop", "summary": "loop"}]},
    )
    assert "#project/P" in tags
    assert "## Evidence" in body


def test_update_patterns_index_dedupes(run_tree):
    _, project_dir, _ = run_tree
    update_patterns_index(project_dir, run_id="r1", tags=["#project/X"], title="T1")
    update_patterns_index(project_dir, run_id="r1", tags=["#project/X"], title="T2")
    patterns_dir = project_dir / "knowledge" / "patterns"
    index_yaml = patterns_dir / "index.yaml"
    index_json = patterns_dir / "index.json"
    index_text = ""
    if index_yaml.is_file():
        index_text = index_yaml.read_text(encoding="utf-8")
    elif index_json.is_file():
        index_text = index_json.read_text(encoding="utf-8")
    assert index_text.count("r1") >= 1
    assert "T2" in index_text