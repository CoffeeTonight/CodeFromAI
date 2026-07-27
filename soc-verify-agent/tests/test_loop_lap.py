"""loop_lap — scenario setter and loop_metrics builder."""

from __future__ import annotations

from pathlib import Path

from soc_verify.loop_lap import build_loop_metrics, set_training_scenario, VALID_SCENARIOS

ROOT = Path(__file__).resolve().parents[1]


def test_set_training_scenario_writes_yaml(tmp_path: Path):
    project_dir = tmp_path / "MINI-SOC"
    project_dir.mkdir()
    path = set_training_scenario(project_dir, "env_fail")
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "env_fail" in text


def test_build_loop_metrics_shape():
    status = {
        "finished": True,
        "last_completed_node": "finalize",
        "state": {
            "run_id": "lap-1",
            "verdict": "PASS",
            "run_profile": "training",
        },
    }
    metrics = build_loop_metrics(
        root=ROOT,
        project_id="MINI-SOC",
        stage="simulation",
        group="mini_gate",
        profile="training",
        scenario="pass",
        session_id="sess-1",
        status=status,
        tick_count=8,
        elapsed_s=12.5,
    )
    assert metrics["contract"] == "loop_metrics_v1"
    assert metrics["tick_count"] == 8
    assert metrics["verdict"] == "PASS"
    assert metrics["scenario"] == "pass"
    assert set(VALID_SCENARIOS) == {"pass", "env_fail", "verif_fail"}