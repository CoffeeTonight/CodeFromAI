"""E2E — soc-verify lap on MINI-SOC pass scenario."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from soc_verify.loop_lap import LOOP_METRICS_NAME, run_training_lap

pytestmark = pytest.mark.e2e

ROOT = Path(__file__).resolve().parents[1]
MINI = ROOT / "projects" / "MINI-SOC"


def test_mini_soc_training_lap_pass():
    result = run_training_lap(
        ROOT,
        project_id="MINI-SOC",
        stage="simulation",
        group="mini_gate",
        profile="training",
        scenario="pass",
        max_ticks=25,
    )
    metrics = result.get("loop_metrics") or {}
    assert result.get("ok") is True, json.dumps(result, indent=2, default=str)
    assert metrics.get("verdict") == "PASS"
    assert metrics.get("scenario") == "pass"
    assert metrics.get("tick_count", 99) <= 20
    run_id = metrics.get("run_id")
    assert run_id
    metrics_path = MINI / "runs" / run_id / LOOP_METRICS_NAME
    assert metrics_path.is_file()
    assert (MINI / "runs" / run_id / "weakness_report.json").is_file()