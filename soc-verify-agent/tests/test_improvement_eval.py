from __future__ import annotations

import json
import uuid
from datetime import date
from pathlib import Path

from soc_verify.improvement_eval import (
    append_history,
    build_snapshot,
    collect_run_signals,
    load_history,
    summarize_trend,
    write_improvement_signal,
    write_improvement_snapshot,
)


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "projects" / "EXAMPLE-SOC"


def _signals(**overrides) -> dict:
    base = {
        "run_id": "run-test",
        "project_id": "EXAMPLE-SOC",
        "stage": "simulation",
        "group": "gpio_ext",
        "verdict": "PASS",
        "completeness": 0.85,
        "trust_score": 0.8,
        "runner": "python",
        "runner_mode": "python_canonical",
        "fix_round": 0,
        "codegen_round": 0,
        "bridge_round": 0,
        "error_kind": "none",
        "parity_ok": True,
        "llm_node_count": 1,
        "graph_step_count": 8,
        "stalemate": False,
        "promoted": True,
        "llm_fix_rounds": 0,
        "tool_incidents": 0,
        "env_fail_steps": 0,
    }
    base.update(overrides)
    return base


def test_build_snapshot_improvement_index_increases_on_pass(tmp_path: Path):
    project_dir = tmp_path / "KPI-TEST"
    project_dir.mkdir()
    run_dir = project_dir / "runs" / f"imp-{uuid.uuid4().hex[:8]}"
    run_dir.mkdir(parents=True)
    signals = _signals(project_id="KPI-TEST", stage="unit", group="snap")
    snap = build_snapshot(project_dir, run_dir, signals, as_of="2026-06-15")
    assert 0.0 < snap.improvement_index <= 1.0
    assert snap.verdict == "PASS"
    assert snap.delta_vs_previous == {}


def test_history_delta_vs_previous():
    run_dir = EXAMPLE / "runs" / f"imp-hist-{uuid.uuid4().hex[:8]}"
    run_dir.mkdir(parents=True, exist_ok=True)
    stage, group = "simulation", "gpio_ext"

    first = build_snapshot(EXAMPLE, run_dir, _signals(verdict="FAIL", completeness=0.5), as_of="2026-06-14")
    append_history(EXAMPLE, first)
    second = build_snapshot(EXAMPLE, run_dir, _signals(verdict="PASS", completeness=0.9), as_of="2026-06-15")
    append_history(EXAMPLE, second)

    history = load_history(EXAMPLE, stage, group)
    assert len(history) >= 2
    last = history[-1]
    assert last["verdict"] == "PASS"
    assert last.get("delta_vs_previous", {}).get("verdict_pass", 0) > 0


def test_summarize_trend_improving():
    run_dir = EXAMPLE / "runs" / f"imp-trend-{uuid.uuid4().hex[:8]}"
    run_dir.mkdir(parents=True, exist_ok=True)
    stage, group = "simulation", "gpio_ext"

    low = build_snapshot(EXAMPLE, run_dir, _signals(completeness=0.5), as_of="2026-06-13")
    high = build_snapshot(EXAMPLE, run_dir, _signals(completeness=0.95), as_of="2026-06-14")
    append_history(EXAMPLE, low)
    append_history(EXAMPLE, high)

    trend = summarize_trend(EXAMPLE, stage, group)
    assert trend["trend"] in ("improving", "regressing")
    assert trend["runs"] >= 2


def test_collect_run_signals_from_trace(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "graph_trace.jsonl").write_text(
        '{"node":"run_gate"}\n{"node":"meta_propose"}\n',
        encoding="utf-8",
    )
    state = {
        "run_id": "r1",
        "project_id": "P",
        "stage": "sim",
        "group": "g",
        "verdict": "PASS",
        "events": {"llm_fix_rounds": 1, "tool_incidents": 0, "env_fail_steps": 0},
    }
    signals = collect_run_signals(run_dir, state)
    assert signals["llm_node_count"] == 2  # run_gate + meta_propose in trace
    assert signals["graph_step_count"] == 2

    write_improvement_signal(run_dir, signals)
    snap = build_snapshot(EXAMPLE, run_dir, signals)
    write_improvement_snapshot(run_dir, snap)
    assert (run_dir / "improvement_signal.json").is_file()
    assert json.loads((run_dir / "improvement_snapshot.json").read_text())["improvement_index"] >= 0