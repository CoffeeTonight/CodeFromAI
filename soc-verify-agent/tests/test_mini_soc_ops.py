"""MINI-SOC scenario ops — pass / env_fail / verif_fail."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from soc_verify.bridge_env import classify_gate_failure
from soc_verify.constants import EXIT_BLOCKED, EXIT_FAIL, EXIT_PASS
from soc_verify.loop_lap import set_training_scenario
from soc_verify.models import load_yaml
from soc_verify.runner import run_python_script

ROOT = Path(__file__).resolve().parents[1]
MINI = ROOT / "projects" / "MINI-SOC"
OPS = MINI / "ops" / "simulation" / "mini_gate.py"


@pytest.mark.parametrize(
    "scenario,expected_status,expected_exit",
    [
        ("pass", "PASS", EXIT_PASS),
        ("env_fail", "BLOCKED", EXIT_BLOCKED),
        ("verif_fail", "FAIL", EXIT_FAIL),
    ],
)
def test_mini_gate_scenarios(tmp_path: Path, scenario: str, expected_status: str, expected_exit: int):
    project_dir = tmp_path / "MINI-SOC"
    run_dir = project_dir / "runs" / "r-scenario"
    run_dir.mkdir(parents=True)
    set_training_scenario(project_dir, scenario)

    proc = subprocess.run(
        [sys.executable, str(OPS), "--project", str(project_dir), "--run-dir", str(run_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == expected_exit, proc.stderr

    verdict_path = run_dir / "verdict_mini_gate.json"
    assert verdict_path.is_file()
    data = json.loads(verdict_path.read_text(encoding="utf-8"))
    assert data["status"] == expected_status
    assert data["scenario"] == scenario


def test_classify_env_fail_as_env(tmp_path: Path):
    project_dir = tmp_path / "MINI-SOC"
    run_dir = project_dir / "runs" / "r-env"
    run_dir.mkdir(parents=True)
    set_training_scenario(project_dir, "env_fail")
    from soc_verify.models import Verdict

    verdict = run_python_script(OPS, project_dir=project_dir, run_dir=run_dir, gate="mini_gate")
    assert verdict.status == "BLOCKED"
    assert classify_gate_failure(verdict=verdict) == "env"


def test_classify_verif_fail_as_verification(tmp_path: Path):
    project_dir = tmp_path / "MINI-SOC"
    run_dir = project_dir / "runs" / "r-verif"
    run_dir.mkdir(parents=True)
    set_training_scenario(project_dir, "verif_fail")
    verdict = run_python_script(OPS, project_dir=project_dir, run_dir=run_dir, gate="mini_gate")
    assert verdict.status == "FAIL"
    assert classify_gate_failure(verdict=verdict) == "verification"