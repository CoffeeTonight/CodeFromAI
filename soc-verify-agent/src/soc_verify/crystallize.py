"""Crystallize successful LLM logic into per-project Python ops (Compiled AI path)."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from soc_verify.stages import ops_script_path


_PY_BLOCK = re.compile(r"```python\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_python_from_proposal(text: str) -> str | None:
    blocks = _PY_BLOCK.findall(text)
    if not blocks:
        return None
    return blocks[-1].strip()


def load_crystallize_proposal(run_dir: Path) -> str:
    for name in ("crystallize_proposal.md", "crystallize_proposal.txt"):
        p = run_dir / name
        if p.is_file():
            return p.read_text(encoding="utf-8")
    return ""


def apply_crystallize_proposal(
    project_dir: Path,
    stage: str,
    group: str,
    run_dir: Path,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """
    Write ops/{stage}/{group}.py from LLM crystallize_proposal.md fenced python block.
    Only called after promote approval (registry_writer gate upstream).
    """
    proposal = load_crystallize_proposal(run_dir)
    code = extract_python_from_proposal(proposal)
    if not code:
        return {"applied": False, "reason": "no_python_block_in_crystallize_proposal"}

    target = ops_script_path(project_dir, stage, group)
    if target.is_file() and not force:
        return {"applied": False, "reason": "ops_script_exists", "path": str(target)}

    header = (
        f'#!/usr/bin/env python3\n"""Crystallized from run {run_dir.name} on {date.today().isoformat()}."""\n\n'
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(header + code + "\n", encoding="utf-8")
    target.chmod(0o755)

    record = project_dir / "patterns" / f"crystallize_{group}_{run_dir.name}.md"
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(
        f"# Crystallized — {stage}/{group}\n\nsource_run: {run_dir.name}\npath: {target}\n",
        encoding="utf-8",
    )

    root = project_dir.parent.parent
    try:
        from soc_verify.platform_telemetry import record_code_change

        record_code_change(
            root,
            run_id=run_dir.name,
            project_id=project_dir.name,
            layer="ops",
            target=str(target.relative_to(project_dir)),
            rationale="crystallize_proposal",
            source="crystallize",
            applied=True,
        )
    except Exception:
        pass

    return {"applied": True, "path": str(target), "run_id": run_dir.name}