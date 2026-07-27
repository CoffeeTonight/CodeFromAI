#!/usr/bin/env python3
"""MINI-SOC scenario gate — pass | env_fail | verif_fail via meta/training_scenario.yaml."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from soc_verify.constants import EXIT_BLOCKED, EXIT_FAIL, EXIT_PASS
from soc_verify.models import load_yaml

SCENARIO_FILE = "meta/training_scenario.yaml"
VALID_SCENARIOS = frozenset({"pass", "env_fail", "verif_fail"})


def _load_scenario(project_dir: Path) -> str:
    path = project_dir / SCENARIO_FILE
    if not path.is_file():
        return "pass"
    data = load_yaml(path)
    scenario = str(data.get("scenario") or "pass").strip()
    return scenario if scenario in VALID_SCENARIOS else "pass"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True)
    p.add_argument("--run-dir", required=True)
    args = p.parse_args()

    project_dir = Path(args.project)
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    scenario = _load_scenario(project_dir)

    if scenario == "pass":
        verdict = {
            "gate": "mini_gate",
            "status": "PASS",
            "exit_code": EXIT_PASS,
            "evidence": ["mini_gate scenario=pass"],
            "artifacts": {},
            "trust": {"script": "mini_gate.py", "version": "0.1.0"},
        }
        exit_code = EXIT_PASS
    elif scenario == "env_fail":
        verdict = {
            "gate": "mini_gate",
            "status": "BLOCKED",
            "exit_code": EXIT_BLOCKED,
            "evidence": ["simulator license missing (scenario=env_fail)"],
            "metrics": {"failure_kind": "env"},
            "artifacts": {},
        }
        exit_code = EXIT_BLOCKED
    else:
        verdict = {
            "gate": "mini_gate",
            "status": "FAIL",
            "exit_code": EXIT_FAIL,
            "evidence": ["tier marker T1 missing (scenario=verif_fail)"],
            "artifacts": {},
        }
        exit_code = EXIT_FAIL

    verdict["scenario"] = scenario
    out = run_dir / "verdict_mini_gate.json"
    out.write_text(json.dumps(verdict, indent=2), encoding="utf-8")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())