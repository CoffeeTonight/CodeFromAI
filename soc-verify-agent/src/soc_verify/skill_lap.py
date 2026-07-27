"""SKILL → materialize → bootstrap → training verify lap (one command)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from soc_verify.loop_lap import run_training_lap
from soc_verify.skill_materialize import (
    bootstrap_group_ops,
    ensure_verify_handoff,
    materialize_from_skill,
    primary_materialized_group,
)
from soc_verify.skill_registry import get_skill, register_skill


def run_skill_lap(
    root: Path,
    *,
    project_id: str,
    skill_id: str = "",
    skill_file: Path | None = None,
    profile: str = "training",
    max_ticks: int = 30,
    overwrite: bool = True,
) -> dict[str, Any]:
    """Register (optional) → materialize one SKILL → ops bootstrap → training lap."""
    root = root.resolve()
    project_dir = root / "projects" / project_id
    if not project_dir.is_dir():
        raise FileNotFoundError(f"project not found: {project_dir}")

    resolved_skill_id = skill_id.strip()
    if skill_file:
        body = Path(skill_file).read_text(encoding="utf-8")
        registered = register_skill(project_dir, name=skill_id or Path(skill_file).stem, body=body)
        resolved_skill_id = str(registered.get("id") or skill_id)
    elif not resolved_skill_id:
        raise ValueError("provide --skill or --skill-file")

    skill_entry = get_skill(project_dir, resolved_skill_id)
    if not skill_entry:
        raise FileNotFoundError(f"skill not found: {resolved_skill_id}")

    materialized = materialize_from_skill(
        project_dir,
        skill_entry,
        overwrite=overwrite,
    )
    if not materialized.get("materialized"):
        return {
            "ok": False,
            "skill_id": resolved_skill_id,
            "materialized": materialized,
            "error": materialized.get("reason", "not_materialized"),
        }

    stage = str(materialized["stage"])
    group = str(materialized["group"])
    bootstrap = bootstrap_group_ops(project_dir, stage=stage, group=group)
    handoff_dir = project_dir / "runs" / "skill_lap_handoff"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    ensure_verify_handoff(project_dir, stage=stage, group=group, run_dir=handoff_dir)

    lap = run_training_lap(
        root,
        project_id=project_id,
        stage=stage,
        group=group,
        profile=profile,
        scenario="pass",
        max_ticks=max_ticks,
    )

    primary = primary_materialized_group([materialized])
    return {
        "ok": lap.get("ok"),
        "skill_id": resolved_skill_id,
        "materialized": materialized,
        "ops_bootstrap": bootstrap,
        "primary_group": primary,
        "lap": lap,
    }