"""Environment discovery orchestrator — three pure stages, no project hardcoding."""
# goal_build_id = 12

from __future__ import annotations

from pathlib import Path
from typing import Any

from socverif.constants import PIPELINE_STAGES
from socverif.discovery.eda_stage import detect_eda
from socverif.discovery.manifest_stage import compose_manifest
from socverif.discovery.structure_stage import scan_structure
from socverif.user_manifest import load_user_overlay


def scan_environment(root: Path) -> dict[str, Any]:
    """Discover any SoC sim environment: EDA -> structure -> manifest (+ adapter)."""
    root = root.resolve()
    overlay = load_user_overlay(root)
    exclude = frozenset(overlay.get("scan_exclude_dirs", []))
    eda = detect_eda(root, exclude_dirs=exclude)
    structure = scan_structure(root, exclude_dirs=exclude)
    manifest = compose_manifest(root, eda, structure, exclude_dirs=exclude)
    manifest["pipeline"] = list(PIPELINE_STAGES)
    return manifest