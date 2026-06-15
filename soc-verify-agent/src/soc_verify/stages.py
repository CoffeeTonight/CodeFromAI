"""Verification stage registry and path resolution."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from soc_verify.models import load_yaml

VALID_STAGES = ("sanity", "consistency", "static", "simulation", "regression")


def load_stages_registry(root: Path | None = None) -> dict[str, Any]:
    root = root or Path.cwd()
    path = root / "registry" / "verification_stages.yaml"
    if not path.is_file():
        path = Path(__file__).resolve().parents[2] / "registry" / "verification_stages.yaml"
    return load_yaml(path)


def is_valid_stage(stage: str) -> bool:
    return stage in VALID_STAGES


def verification_group_dir(project_dir: Path, stage: str, group: str) -> Path:
    if not is_valid_stage(stage):
        raise ValueError(f"Invalid stage: {stage}. Must be one of {VALID_STAGES}")
    return project_dir / "verification" / stage / group


def ops_script_path(project_dir: Path, stage: str, group: str) -> Path:
    return project_dir / "ops" / stage / f"{group}.py"


def find_group_dir(project_dir: Path, stage: str, group: str) -> Path | None:
    d = verification_group_dir(project_dir, stage, group)
    return d if d.is_dir() else None


def resolve_group_script(project_dir: Path, stage: str, group: str) -> Path | None:
    """ops/{stage}/{group}.py 우선, legacy ops/groups/, verification run.py."""
    candidates = [
        ops_script_path(project_dir, stage, group),
        project_dir / "ops" / "groups" / f"{group}.py",
    ]
    vdir = verification_group_dir(project_dir, stage, group)
    if vdir.is_dir():
        candidates.append(vdir / "run.py")

    for c in candidates:
        if c.is_file():
            return c
    return None


def stage_depends_on(stage: str, root: Path | None = None) -> list[str]:
    reg = load_stages_registry(root)
    stages = reg.get("stages") or {}
    block = stages.get(stage) or {}
    return list(block.get("depends_on") or [])


def list_groups_in_stage(project_dir: Path, stage: str) -> list[str]:
    base = project_dir / "verification" / stage
    if not base.is_dir():
        return []
    return sorted(
        d.name for d in base.iterdir() if d.is_dir() and (d / "manifest.yaml").is_file()
    )