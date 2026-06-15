"""Deterministic milestone gate before verify."""

from __future__ import annotations

import re
from typing import Any


_M_RE = re.compile(r"^M(\d+)$", re.I)


def milestone_index(milestone: str) -> int | None:
    m = _M_RE.match(str(milestone).strip())
    return int(m.group(1)) if m else None


def check_milestone_gate(
    manifest: dict[str, Any],
    state: dict[str, Any],
    *,
    group_status: str = "",
) -> tuple[bool, str]:
    """
    Block verify when group targets a future design milestone.
    scheduled + same milestone as current is allowed.
    """
    manifest_m = manifest.get("milestone", "")
    current_m = state.get("current_milestone", "")
    mi = milestone_index(str(manifest_m))
    ci = milestone_index(str(current_m))

    if mi is None:
        return False, f"Invalid manifest.milestone: {manifest_m!r}"
    if ci is None:
        return False, f"Invalid state.current_milestone: {current_m!r}"

    if mi > ci:
        return (
            False,
            f"Group milestone {manifest_m} ahead of project current_milestone {current_m}",
        )

    status = group_status or manifest.get("status", "")
    if status == "scheduled" and mi < ci:
        return (
            False,
            f"Group status scheduled but milestone {manifest_m} behind current {current_m}",
        )

    return True, ""