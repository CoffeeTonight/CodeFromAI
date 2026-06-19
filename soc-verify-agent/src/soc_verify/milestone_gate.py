"""Deterministic milestone gate before verify."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from soc_verify.milestone_plans import (
    load_plan,
    milestone_rank,
    normalize_milestone_id,
    resolve_canonical_id,
    resolve_schedule_context,
)


def milestone_index(milestone: str, *, state: dict[str, Any] | None = None, root: Path | None = None) -> int | None:
    """Return 0-based rank for a milestone id (backward-compatible name)."""
    if state is None:
        import re

        m = re.compile(r"^M(\d+)$", re.I).match(str(milestone).strip())
        return int(m.group(1)) - 1 if m else None
    ctx = resolve_schedule_context(state, root)
    plan = load_plan(root, ctx.plan_id) if root and ctx.plan_id != "custom" else None
    return milestone_rank(milestone, ctx, plan)


def check_milestone_gate(
    manifest: dict[str, Any],
    state: dict[str, Any],
    *,
    group_status: str = "",
    root: Path | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    """
    Block verify when group targets a future design milestone.
    scheduled + same milestone as current is allowed.

    Ordering comes from schedule_plan registry and/or project state.yaml milestones.
    """
    manifest_m = normalize_milestone_id(str(manifest.get("milestone", "")))
    current_m = normalize_milestone_id(str(state.get("current_milestone", "")))

    if not manifest_m:
        return False, "Missing manifest.milestone"
    if not current_m:
        return False, "Missing state.current_milestone"

    ctx = resolve_schedule_context(state, root, config=config)
    plan = load_plan(root, ctx.plan_id) if root and ctx.plan_id != "custom" else None

    mi = milestone_rank(manifest_m, ctx, plan)
    ci = milestone_rank(current_m, ctx, plan)

    if mi is None:
        canon = resolve_canonical_id(manifest_m, ctx, plan)
        hint = f" (plan: {ctx.plan_id}, known: {ctx.ordered_ids})"
        return False, f"Unknown manifest.milestone: {manifest_m!r}{hint}"
    if ci is None:
        return False, f"Unknown state.current_milestone: {current_m!r} (plan: {ctx.plan_id})"

    manifest_canon = resolve_canonical_id(manifest_m, ctx, plan)
    current_canon = resolve_canonical_id(current_m, ctx, plan)

    if mi > ci:
        return (
            False,
            f"Group milestone {manifest_canon} ahead of project current_milestone {current_canon}",
        )

    status = group_status or manifest.get("status", "")
    if status == "scheduled" and mi < ci:
        return (
            False,
            f"Group status scheduled but milestone {manifest_canon} behind current {current_canon}",
        )

    return True, ""