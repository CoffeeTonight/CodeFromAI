"""Verification reproduction shell scripts — LangGraph finalize contract."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

_STEP_SCRIPT_RE = re.compile(r"^\d{2}_.+\.sh$")


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def sequence_path(project_dir: Path) -> Path:
    return project_dir / "scripts" / "verification_sequence.yaml"


def load_sequence(project_dir: Path) -> dict[str, Any]:
    path = sequence_path(project_dir)
    return _load_yaml(path) if path.is_file() else {}


def step_for_gate(sequence: dict[str, Any], stage: str, group: str) -> dict[str, Any] | None:
    for step in sequence.get("steps") or []:
        if step.get("stage") == stage and step.get("group") == group:
            return step
    return None


def validate_gate_step(project_dir: Path, stage: str, group: str) -> dict[str, Any]:
    """Check step script + verification_sequence entry for one gate."""
    scripts_dir = project_dir / "scripts"
    sequence = load_sequence(project_dir)
    step = step_for_gate(sequence, stage, group)
    issues: list[str] = []
    script_name = ""
    script_path: Path | None = None

    if not step:
        issues.append(f"verification_sequence.yaml missing step for {stage}/{group}")
    else:
        script_name = str(step.get("script", ""))
        if not script_name:
            issues.append("step.script empty")
        else:
            script_path = scripts_dir / script_name
            if not script_path.is_file():
                issues.append(f"missing step script: scripts/{script_name}")
            elif not _STEP_SCRIPT_RE.match(script_name):
                issues.append(f"step script name must match NN_*.sh: {script_name}")

    readme = scripts_dir / "README.md"
    if not readme.is_file():
        issues.append("missing scripts/README.md")

    return {
        "ok": not issues,
        "stage": stage,
        "group": group,
        "step": step,
        "script": script_name,
        "script_path": str(script_path) if script_path else "",
        "issues": issues,
    }


def validate_orchestrator(project_dir: Path) -> dict[str, Any]:
    """Check full-sequence orchestrator + reports linkage."""
    project_id = project_dir.name
    scripts_dir = project_dir / "scripts"
    sequence = load_sequence(project_dir)
    issues: list[str] = []

    orch_name = str(sequence.get("orchestrator") or f"run_{project_id}_verification_sequence.sh")
    orch_path = scripts_dir / orch_name
    if not orch_path.is_file():
        issues.append(f"missing orchestrator: scripts/{orch_name}")

    reports_script = str(sequence.get("reports_script") or "99_generate_verification_reports.sh")
    if not (scripts_dir / reports_script).is_file():
        issues.append(f"missing reports script: scripts/{reports_script}")

    steps = sequence.get("steps") or []
    if not steps:
        issues.append("verification_sequence.yaml has no steps")

    for step in steps:
        script = str(step.get("script", ""))
        if script and not (scripts_dir / script).is_file():
            issues.append(f"missing step script: scripts/{script}")

    index_path = project_dir / "reports" / "index.yaml"
    if index_path.is_file():
        index = _load_yaml(index_path)
        vs = index.get("verification_sequence") or {}
        if not vs.get("orchestrator"):
            issues.append("reports/index.yaml missing verification_sequence.orchestrator")
    else:
        issues.append("missing reports/index.yaml")

    return {
        "ok": not issues,
        "project_id": project_id,
        "orchestrator": orch_name,
        "steps_count": len(steps),
        "issues": issues,
    }


def build_gate_reproduction_prompt(
    *,
    project_dir: Path,
    stage: str,
    group: str,
    run_id: str,
    verdict_path: str,
) -> dict[str, Any]:
    sequence = load_sequence(project_dir)
    step = step_for_gate(sequence, stage, group)
    validation = validate_gate_step(project_dir, stage, group)
    return {
        "contract": "reproduction_finalize_gate",
        "project_id": project_dir.name,
        "stage": stage,
        "group": group,
        "run_id": run_id,
        "verdict_path": verdict_path,
        "verification_title": (step or {}).get("verification_title", ""),
        "existing_step": step,
        "validation": validation,
        "rules_template": "templates/scripts/README.md",
        "project_scripts_readme": "scripts/README.md",
        "required_writes": [
            f"scripts/{{NN}}_{stage}_<title_slug>.sh",
            "scripts/verification_sequence.yaml (append or update step)",
            f"runs/{run_id}/reproduction_finalize.json",
        ],
        "forbidden": [
            "gate CLI options on orchestrator (e.g. ./run.sh coi_conn)",
            "per-gate reproduce_script in reports/index.yaml",
        ],
    }


def build_sequence_reproduction_prompt(
    *,
    project_dir: Path,
    verify_results: list[dict[str, Any]],
) -> dict[str, Any]:
    validation = validate_orchestrator(project_dir)
    sequence = load_sequence(project_dir)
    return {
        "contract": "reproduction_finalize_sequence",
        "project_id": project_dir.name,
        "verify_results": verify_results,
        "sequence_steps": sequence.get("steps") or [],
        "validation": validation,
        "rules_template": "templates/scripts/README.md",
        "required_writes": [
            f"scripts/run_{project_dir.name}_verification_sequence.sh",
            "scripts/99_generate_verification_reports.sh",
            "scripts/verification_sequence.yaml",
            "reports/index.yaml → verification_sequence block",
            "runs/orchestrator/{run_id}/reproduction_sequence_finalize.json",
        ],
        "rules": [
            "Orchestrator has no CLI args — bash each step in verified order",
            "Filename encodes verification title (NN_stage_title.sh)",
        ],
    }


def write_gate_reproduction_prompt(run_dir: Path, payload: dict[str, Any]) -> Path:
    path = run_dir / "reproduction_finalize_prompt.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_sequence_reproduction_prompt(orch_run_dir: Path, payload: dict[str, Any]) -> Path:
    path = orch_run_dir / "reproduction_sequence_prompt.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path