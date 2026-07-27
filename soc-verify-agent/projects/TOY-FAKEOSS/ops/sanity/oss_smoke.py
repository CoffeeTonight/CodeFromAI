#!/usr/bin/env python3
"""Toy OSS smoke gate — auto-scaffolded from intake (scenario-aware)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from soc_verify.constants import EXIT_BLOCKED, EXIT_FAIL, EXIT_PASS
from soc_verify.models import load_yaml

GATE = "oss_smoke"
SCENARIO_FILE = "meta/training_scenario.yaml"
TOY_GATE_FILE = "meta/toy_gate.yaml"
VALID_SCENARIOS = frozenset({"pass", "env_fail", "verif_fail"})


def _load_scenario(project_dir: Path) -> str:
    path = project_dir / SCENARIO_FILE
    if not path.is_file():
        return "pass"
    data = load_yaml(path)
    scenario = str(data.get("scenario") or "pass").strip()
    return scenario if scenario in VALID_SCENARIOS else "pass"


def _toy_gate(project_dir: Path) -> dict:
    data = load_yaml(project_dir / TOY_GATE_FILE) or {}
    return data


def _resolve_rtl(project_dir: Path) -> Path:
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from ops.intake_resolve import resolve_rtl_root

    return resolve_rtl_root(project_dir)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True)
    p.add_argument("--run-dir", required=True)
    args = p.parse_args()

    project_dir = Path(args.project)
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    scenario = _load_scenario(project_dir)
    cfg = _toy_gate(project_dir)
    required = list(cfg.get("required_artifacts") or [])
    env_msg = str(cfg.get("env_fail_evidence") or "simulator license missing (scenario=env_fail)")
    verif_msg = str(cfg.get("verif_fail_evidence") or "required build artifact missing (scenario=verif_fail)")

    if scenario == "env_fail":
        verdict = {
            "gate": GATE,
            "status": "BLOCKED",
            "exit_code": EXIT_BLOCKED,
            "evidence": [env_msg],
            "metrics": {"failure_kind": "env"},
            "artifacts": {},
        }
        exit_code = EXIT_BLOCKED
    elif scenario == "verif_fail":
        verdict = {
            "gate": GATE,
            "status": "FAIL",
            "exit_code": EXIT_FAIL,
            "evidence": [verif_msg],
            "artifacts": {},
        }
        exit_code = EXIT_FAIL
    else:
        rtl_root = _resolve_rtl(project_dir)
        present = [rel for rel in required if (rtl_root / rel).exists()]
        missing = [rel for rel in required if rel not in present]
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
                    f"OSS smoke OK rtl_root={rtl_root}",
                    f"artifacts_present={len(present)}",
                    f"source={cfg.get('source_id', '')}",
                ],
                "artifacts": {
                    "rtl_root": str(rtl_root),
                    "root_marker": str(rtl_root / str(cfg.get("root_marker") or "example.sh")),
                },
                "trust": {"script": "oss_smoke.py", "version": "0.1.0"},
            }
            exit_code = EXIT_PASS

    verdict["scenario"] = scenario
    out = run_dir / f"verdict_{GATE}.json"
    out.write_text(json.dumps(verdict, indent=2), encoding="utf-8")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
