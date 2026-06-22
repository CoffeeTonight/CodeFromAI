from __future__ import annotations

from pathlib import Path

from soc_verify.loop_guard import (
    detect_stagnation_pattern,
    record_drift_score,
    record_transition,
)

ROOT = Path(__file__).resolve().parents[1]


def test_oscillation_pattern(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    record_transition(run_dir, "run_gate", error_kind="verification")
    record_transition(run_dir, "diagnose_env", error_kind="env")
    record_transition(run_dir, "run_gate", error_kind="verification")
    state = record_transition(run_dir, "diagnose_env", error_kind="env")
    assert state.stalemate is True
    assert state.stalemate_pattern == "OSCILLATION"


def test_no_drift_pattern(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    record_drift_score(run_dir, 0.15)
    record_drift_score(run_dir, 0.15)
    state = record_drift_score(run_dir, 0.15)
    assert state.stalemate is True
    assert state.stalemate_pattern == "NO_DRIFT"


def test_detect_oscillation_helper():
    t = ["run_gate:verification", "diagnose_env:env", "run_gate:verification", "diagnose_env:env"]
    assert detect_stagnation_pattern(t) == "OSCILLATION"