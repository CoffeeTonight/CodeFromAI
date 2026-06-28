"""Toy-first policy — require short-TAT mimic before full user SoC."""
# goal_build_id = 12

from __future__ import annotations

import sys
from pathlib import Path

from socverif.paths import is_self_harness_root

REFERENCE_TOYS = frozenset({
    "minimal_soc",
    "alt_soc",
    "script_only_soc",
    "synthetic_vcs_style",
    "toy_mimic_soc",
})


def is_toy_env(root: Path) -> bool:
    root = root.resolve()
    if is_self_harness_root(root):
        return True
    if root.name in REFERENCE_TOYS:
        return True
    if (root / ".socverif" / "toy_mimic.yaml").is_file():
        return True
    return False


def check_toy_first(root: Path, allow_full_soc: bool = False, command: str = "run") -> None:
    """Exit with guidance when targeting a non-toy user SoC without opt-in."""
    if allow_full_soc or is_toy_env(root):
        return
    print(
        f"[toy_policy] BLOCKED: {command} on non-toy env '{root.name}'.\n"
        "  Create/use a short-TAT toy mimic first (see docs/soc_validation_flow.md §0).\n"
        "  Example: python3 -m socverif.cli loop envs/toy_mimic_soc --max-tier 2\n"
        "  Override: --allow-full-soc (only after toy PASS)",
        file=sys.stderr,
    )
    sys.exit(2)