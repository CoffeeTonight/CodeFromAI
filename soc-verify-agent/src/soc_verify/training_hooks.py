"""Training-profile hooks — auto_apply node guides on finalize."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from soc_verify.node_guide import materialize_all


def apply_training_node_guides(
    root: Path,
    project_dir: Path,
    *,
    run_profile: str,
) -> dict[str, Any]:
    """Re-materialize registered node guides when training profile requests auto_apply."""
    from soc_verify.run_profile import should_auto_apply_node_guides

    if not should_auto_apply_node_guides(root, run_profile):
        return {"ok": True, "applied": False, "reason": "profile_disabled", "results": []}

    results = materialize_all(project_dir, root=root)
    return {
        "ok": True,
        "applied": True,
        "count": len(results),
        "results": results,
    }