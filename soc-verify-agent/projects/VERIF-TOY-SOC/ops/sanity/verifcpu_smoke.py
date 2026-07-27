#!/usr/bin/env python3
"""VERIF-TOY-SOC — lightweight VerifCPU OSS smoke (no full compile).

Scenarios via meta/training_scenario.yaml: pass | env_fail | verif_fail
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from soc_verify.constants import EXIT_BLOCKED, EXIT_FAIL, EXIT_PASS
from soc_verify.models import load_yaml

GATE = "verifcpu_smoke"
SCENARIO_FILE = "meta/training_scenario.yaml"
VALID_SCENARIOS = frozenset({"pass", "env_fail", "verif_fail"})

_REQUIRED_ARTIFACTS = (
    "example.sh",
    "Makefile",
    "rtl",
    "firmware",
    "filelists",
    "README.md",
)


def _load_scenario(project_dir: Path) -> str:
    path = project_dir / SCENARIO_FILE
    if not path.is_file():
        return "pass"
    data = load_yaml(path)
    scenario = str(data.get("scenario") or "pass").strip()
    return scenario if scenario in VALID_SCENARIOS else "pass"


def _resolve_rtl(project_dir: Path) -> Path:
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from ops.intake_resolve import resolve_rtl_root

    return resolve_rtl_root(project_dir)


def _check_oss_artifacts(rtl_root: Path) -> tuple[list[str], list[str]]:
    present: list[str] = []
    missing: list[str] = []
    for rel in _REQUIRED_ARTIFACTS:
        path = rtl_root / rel
        if path.exists():
            present.append(rel)
        else:
            missing.append(rel)
    return present, missing


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True)
    p.add_argument("--run-dir", required=True)
    args = p.parse_args()

    project_dir = Path(args.project)
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    scenario = _load_scenario(project_dir)

    if scenario == "env_fail":
        verdict = {
            "gate": GATE,
            "status": "BLOCKED",
            "exit_code": EXIT_BLOCKED,
            "evidence": ["iverilog not in PATH (scenario=env_fail)"],
            "metrics": {"failure_kind": "env"},
            "artifacts": {},
        }
        exit_code = EXIT_BLOCKED
    elif scenario == "verif_fail":
        verdict = {
            "gate": GATE,
            "status": "FAIL",
            "exit_code": EXIT_FAIL,
            "evidence": ["tb_full_campaign.vvp missing (scenario=verif_fail)"],
            "artifacts": {},
        }
        exit_code = EXIT_FAIL
    else:
        rtl_root = _resolve_rtl(project_dir)
        present, missing = _check_oss_artifacts(rtl_root)
        if missing:
            verdict = {
                "gate": GATE,
                "status": "FAIL",
                "exit_code": EXIT_FAIL,
                "evidence": [f"missing OSS artifact: {m}" for m in missing],
                "artifacts": {"rtl_root": str(rtl_root)},
            }
            exit_code = EXIT_FAIL
        else:
            verdict = {
                "gate": GATE,
                "status": "PASS",
                "exit_code": EXIT_PASS,
                "evidence": [
                    f"VerifCPU OSS smoke OK rtl_root={rtl_root}",
                    f"artifacts_present={len(present)}",
                ],
                "artifacts": {
                    "rtl_root": str(rtl_root),
                    "example_sh": str(rtl_root / "example.sh"),
                },
                "trust": {"script": "verifcpu_smoke.py", "version": "0.1.0"},
            }
            exit_code = EXIT_PASS

    verdict["scenario"] = scenario
    out = run_dir / f"verdict_{GATE}.json"
    out.write_text(json.dumps(verdict, indent=2), encoding="utf-8")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())