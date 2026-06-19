"""Environment/bridge loop — diagnose env-tool failures, crystallize bridge/*.py."""

from __future__ import annotations

import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Any, Literal

from soc_verify.constants import EXIT_INFO_GAP, EXIT_TOOL_ERROR
from soc_verify.error_classify import classify_stop_report
from soc_verify.models import Verdict, load_yaml, save_yaml


FailureKind = Literal["env", "tool", "info", "llm", "verification", "none"]

BRIDGE_PATCH_NAMES = ("bridge_patch_proposal.md", "bridge_patch.md")
ENV_DIAGNOSIS_NAMES = ("env_diagnosis.md", "env_diagnosis.json")
ENV_PROFILE_NAME = "environment_profile.yaml"


def bridge_script_path(project_dir: Path, stage: str, group: str) -> Path:
    return project_dir / "bridge" / stage / f"{group}.py"


def environment_profile_path(project_dir: Path) -> Path:
    return project_dir / "meta" / ENV_PROFILE_NAME


def load_environment_profile(project_dir: Path) -> dict[str, Any]:
    path = environment_profile_path(project_dir)
    if path.is_file():
        return load_yaml(path)
    legacy = project_dir / "meta.yaml"
    if legacy.is_file():
        data = load_yaml(legacy)
        prof = data.get("environment_profile")
        if isinstance(prof, dict):
            return prof
    return {}


def save_environment_profile(project_dir: Path, profile: dict[str, Any]) -> Path:
    path = environment_profile_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    save_yaml(path, profile)
    return path


def apply_profile_to_environ(project_dir: Path, base: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(base or os.environ)
    profile = load_environment_profile(project_dir)
    for key, val in (profile.get("env") or {}).items():
        env[str(key)] = str(val)
    bridge_root = project_dir / "bridge"
    if bridge_root.is_dir():
        parts = [str(bridge_root)]
        for sub in bridge_root.iterdir():
            if sub.is_dir():
                parts.append(str(sub))
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = os.pathsep.join(parts + ([existing] if existing else []))
    return env


def classify_gate_failure(
    *,
    verdict: Verdict | None = None,
    sub_stop: dict[str, Any] | None = None,
    error: str = "",
) -> FailureKind:
    if sub_stop:
        kind = classify_stop_report(sub_stop)
        if kind in ("env", "tool", "info", "llm"):
            return kind  # type: ignore[return-value]

    if verdict:
        if verdict.status == "INFO_GAP" or verdict.exit_code == EXIT_INFO_GAP:
            return "info"
        if verdict.exit_code == EXIT_TOOL_ERROR:
            return "tool"
        metrics = verdict.metrics or {}
        fk = str(metrics.get("failure_kind", "")).lower()
        if fk in ("env", "tool", "verification"):
            return fk  # type: ignore[return-value]
        if verdict.status == "FAIL":
            return "verification"

    if error == "llm_runner_awaiting_sub_agent":
        return "llm"
    return "verification"


def extract_python_from_proposal(text: str) -> str | None:
    blocks = re.findall(r"```python\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if blocks:
        return blocks[-1].strip()
    blocks = re.findall(r"```\s*\n(.*?)```", text, re.DOTALL)
    if blocks:
        return blocks[-1].strip()
    return None


def load_bridge_patch_proposal(run_dir: Path) -> str:
    for name in BRIDGE_PATCH_NAMES:
        path = run_dir / name
        if path.is_file():
            return path.read_text(encoding="utf-8")
    return ""


def load_env_diagnosis(run_dir: Path) -> dict[str, Any]:
    for name in ENV_DIAGNOSIS_NAMES:
        path = run_dir / name
        if not path.is_file():
            continue
        if name.endswith(".json"):
            return json.loads(path.read_text(encoding="utf-8"))
        return {"format": "markdown", "content": path.read_text(encoding="utf-8")}
    return {}


def build_diagnose_payload(
    *,
    project_dir: Path,
    stage: str,
    group: str,
    run_dir: Path,
    error_kind: str,
    verdict: dict[str, Any] | None = None,
    sub_stop: dict[str, Any] | None = None,
) -> dict[str, Any]:
    log_path = run_dir / f"{group}.log"
    log_tail = ""
    if log_path.is_file():
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        log_tail = "\n".join(lines[-40:])

    return {
        "contract": "env_diagnosis_v1",
        "error_kind": error_kind,
        "project_id": project_dir.name,
        "stage": stage,
        "group": group,
        "bridge_target": str(bridge_script_path(project_dir, stage, group)),
        "environment_profile": str(environment_profile_path(project_dir)),
        "verdict": verdict,
        "sub_stop": sub_stop,
        "log_tail": log_tail,
        "instruction": (
            "Diagnose environment/execution failure only — do not change CHECK pass criteria. "
            "Write env_diagnosis.md with root_cause, evidence, proposed_bridge_changes. "
            "Then write bridge_patch_proposal.md with a ```python``` bridge module."
        ),
    }


def apply_bridge_patch(
    project_dir: Path,
    stage: str,
    group: str,
    run_dir: Path,
    *,
    force: bool = False,
) -> dict[str, Any]:
    proposal = load_bridge_patch_proposal(run_dir)
    code = extract_python_from_proposal(proposal)
    if not code:
        return {"applied": False, "reason": "no_python_block_in_bridge_patch_proposal"}

    target = bridge_script_path(project_dir, stage, group)
    if target.is_file() and not force:
        return {"applied": False, "reason": "bridge_exists", "path": str(target)}

    target.parent.mkdir(parents=True, exist_ok=True)
    header = (
        f'#!/usr/bin/env python3\n"""Bridge patch from run {run_dir.name} on {date.today().isoformat()}."""\n\n'
    )
    target.write_text(header + code + "\n", encoding="utf-8")

    diagnosis = load_env_diagnosis(run_dir)
    if isinstance(diagnosis, dict) and diagnosis.get("environment_profile_patch"):
        profile = load_environment_profile(project_dir)
        patch = diagnosis["environment_profile_patch"]
        if isinstance(patch, dict):
            profile.setdefault("env", {}).update(patch.get("env") or {})
            for key in ("toolchain", "notes"):
                if key in patch:
                    profile[key] = patch[key]
            save_environment_profile(project_dir, profile)

    record = project_dir / "patterns" / f"bridge_{group}_{run_dir.name}.md"
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(proposal[:8000], encoding="utf-8")

    root = project_dir.parent.parent
    try:
        from soc_verify.platform_telemetry import record_code_change

        record_code_change(
            root,
            run_id=run_dir.name,
            project_id=project_dir.name,
            layer="bridge",
            target=str(target.relative_to(project_dir)),
            rationale="bridge_patch_proposal",
            source="patch_bridge",
            applied=True,
        )
    except Exception:
        pass

    return {"applied": True, "path": str(target), "stage": stage, "group": group}


def write_env_diagnosis_prompt(run_dir: Path, payload: dict[str, Any]) -> Path:
    path = run_dir / "env_diagnosis_prompt.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path