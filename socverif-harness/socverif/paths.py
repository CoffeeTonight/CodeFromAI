"""Artifact path resolution — self-harness writes under .socverif/scratch/."""
# goal_build_id = 12

from __future__ import annotations

from pathlib import Path

from socverif.user_manifest import load_user_overlay

SCRATCH_REL = ".socverif/scratch"


def scratch_dir(root: Path) -> Path:
    d = root / SCRATCH_REL
    d.mkdir(parents=True, exist_ok=True)
    return d


def is_self_harness_root(root: Path, manifest_data: dict | None = None) -> bool:
    if manifest_data and manifest_data.get("self_harness"):
        return True
    overlay = load_user_overlay(root)
    return bool(overlay.get("self_harness"))


def manifest_path(root: Path, manifest_data: dict | None = None) -> Path:
    if is_self_harness_root(root, manifest_data):
        return scratch_dir(root) / "environment_manifest.yaml"
    return root / "environment_manifest.yaml"


def report_path(root: Path, manifest_data: dict | None = None) -> Path:
    if is_self_harness_root(root, manifest_data):
        return scratch_dir(root) / "verif_report.json"
    return root / "verif_report.json"