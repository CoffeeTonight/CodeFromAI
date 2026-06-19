"""Execute per-project Python ops or delegate to LLM mode."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from soc_verify.constants import (
    EXIT_FAIL,
    EXIT_INFO_GAP,
    EXIT_PASS,
    EXIT_TOOL_ERROR,
)
from soc_verify.bridge_env import apply_profile_to_environ
from soc_verify.execution_log import append_execution_log, snapshot_run_backup
from soc_verify.models import InfoGapError, Verdict, load_yaml


def run_python_script(
    script_path: Path,
    *,
    project_dir: Path,
    run_dir: Path,
    gate: str,
) -> Verdict:
    if not script_path.is_file():
        raise InfoGapError(f"Script not found: {script_path}", field="script")

    argv = [
        sys.executable,
        str(script_path),
        "--project",
        str(project_dir),
        "--run-dir",
        str(run_dir),
    ]
    proc = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=7200,
        check=False,
        env=apply_profile_to_environ(project_dir),
    )
    append_execution_log(
        run_dir,
        command=argv,
        node="run_gate",
        exit_code=proc.returncode,
        artifact_paths=[str(run_dir / f"verdict_{gate}.json")],
    )

    verdict_path = run_dir / f"verdict_{gate}.json"
    if verdict_path.is_file():
        data = json.loads(verdict_path.read_text(encoding="utf-8"))
        return Verdict.from_dict(data)

    status = "PASS" if proc.returncode == EXIT_PASS else "FAIL"
    if proc.returncode == EXIT_INFO_GAP:
        status = "INFO_GAP"
    elif proc.returncode == EXIT_TOOL_ERROR:
        status = "FAIL"

    evidence = []
    if proc.stderr:
        evidence.append(proc.stderr.strip().splitlines()[-1] if proc.stderr else "")
    if proc.stdout:
        evidence.extend(proc.stdout.strip().splitlines()[-3:])

    verdict = Verdict(
        gate=gate,
        status=status,  # type: ignore[arg-type]
        exit_code=proc.returncode,
        evidence=evidence[:5],
        artifacts={"log": str(run_dir / f"{gate}.log")},
    )
    verdict_path.write_text(json.dumps(verdict.to_dict(), indent=2), encoding="utf-8")
    (run_dir / f"{gate}.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
    snapshot_run_backup(
        run_dir,
        label="run_gate",
        paths=[verdict_path, run_dir / f"{gate}.log"],
    )
    return verdict


def resolve_group_script(project_dir: Path, stage: str, group: str) -> Path | None:
    """Delegate to stages.resolve_group_script (ops/{stage}/{group}.py)."""
    from soc_verify.stages import resolve_group_script as _resolve

    return _resolve(project_dir, stage, group)


def append_question(project_dir: Path, entry: dict[str, Any]) -> None:
    path = project_dir / "questions_pending.md"
    lines = []
    if path.is_file():
        lines.append(path.read_text(encoding="utf-8").rstrip())
    else:
        lines.append("# Pending Questions\n")
        lines.append("| ID | Type | Context | Question | Blocking |")
        lines.append("|----|------|---------|----------|----------|")

    qid = entry.get("id", f"Q{len(lines)}")
    lines.append(
        f"| {qid} | {entry.get('type','')} | {entry.get('context','')} | "
        f"{entry.get('question','')} | {entry.get('blocking','no')} |"
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_run_metrics(run_dir: Path, metrics: dict[str, Any]) -> None:
    (run_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2),
        encoding="utf-8",
    )


def load_active_projects(registry_root: Path, today: str) -> list[str]:
    data = load_yaml(registry_root / "active_projects.yaml")
    search = (data.get("acquisition") or {}).get("project_search") or {}
    if not search.get("fetched_at") and data.get("as_of"):
        search = {**search, "fetched_at": data["as_of"]}
    if search.get("fetched_at", "")[:10] != today:
        pass  # caller should refresh project search when due
    out: list[str] = []
    for p in data.get("projects", []):
        if isinstance(p, dict) and p.get("active"):
            out.append(str(p["id"]))
    return out