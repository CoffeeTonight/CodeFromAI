"""Merge optional `.socverif/manifest.yaml` user overrides into discovered manifest."""
# goal_build_id = 12

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_SELF_HARNESS_KEYS = (
    "project_id",
    "tiers",
    "eda",
    "scripts",
    "capabilities",
    "pass_fail",
    "scan_exclude_dirs",
)


def load_user_overlay(root: Path) -> dict[str, Any]:
    path = root / ".socverif" / "manifest.yaml"
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def merge_user_manifest(manifest: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge user overlay; self_harness mode replaces tier/eda definitions."""
    if not overlay:
        return manifest

    if overlay.get("self_harness"):
        manifest["self_harness"] = True
        for key in _SELF_HARNESS_KEYS:
            if key in overlay:
                manifest[key] = overlay[key]
    else:
        for key in ("tiers", "verification_intents", "pass_fail", "eda", "firmware"):
            if key not in overlay:
                continue
            if isinstance(overlay[key], dict) and isinstance(manifest.get(key), dict):
                merged = dict(manifest.get(key, {}))
                merged.update(overlay[key])
                manifest[key] = merged
            else:
                manifest[key] = overlay[key]

    if overlay.get("scan_notes"):
        manifest["scan_notes"] = manifest.get("scan_notes", []) + list(overlay["scan_notes"])
    manifest["user_overlay"] = True
    manifest["scan_notes"] = manifest.get("scan_notes", []) + [
        "user_manifest: .socverif/manifest.yaml merged"
    ]
    return manifest