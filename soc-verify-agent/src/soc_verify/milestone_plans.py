"""Configurable milestone plans — culture-specific phase ladders."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from soc_verify.models import load_yaml


INDEX_NAME = "index.yaml"
PLANS_DIR = "milestone_plans"
_LEGACY_M_RE = re.compile(r"^M(\d+)$", re.I)
_DEFAULT_PLAN = "soc-dv-4p-v1"


@dataclass
class ScheduleContext:
    plan_id: str
    culture: str
    ordered_ids: list[str]
    id_to_order: dict[str, int] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)
    source: str = "registry"

    def rank(self, milestone_id: str) -> int | None:
        mid = normalize_milestone_id(milestone_id)
        if mid in self.id_to_order:
            return self.id_to_order[mid]
        return self.id_to_order.get(mid.lower())

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "culture": self.culture,
            "source": self.source,
            "ordered_ids": self.ordered_ids,
            "labels": self.labels,
        }


def _registry_dir(root: Path) -> Path:
    return root.resolve() / "registry"


def _plans_dir(root: Path) -> Path:
    return _registry_dir(root) / PLANS_DIR


def normalize_milestone_id(milestone_id: str) -> str:
    return str(milestone_id).strip()


def load_plan_index(root: Path) -> dict[str, Any]:
    path = _plans_dir(root) / INDEX_NAME
    if not path.is_file():
        return {"default_plan": _DEFAULT_PLAN, "plans": []}
    return load_yaml(path) or {}


def default_plan_id(root: Path, config: dict[str, Any] | None = None) -> str:
    if config:
        sched = config.get("schedules") or {}
        if sched.get("default_milestone_plan"):
            return str(sched["default_milestone_plan"])
    idx = load_plan_index(root)
    return str(idx.get("default_plan") or _DEFAULT_PLAN)


def _plan_file_for_id(root: Path, plan_id: str) -> Path | None:
    idx = load_plan_index(root)
    for entry in idx.get("plans") or []:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("id")) == plan_id:
            fname = entry.get("file")
            if not fname:
                return None
            return _plans_dir(root) / str(fname)
    legacy = _plans_dir(root) / f"{plan_id}.yaml"
    return legacy if legacy.is_file() else None


def load_plan(root: Path, plan_id: str) -> dict[str, Any] | None:
    if plan_id == "custom":
        return None
    path = _plan_file_for_id(root, plan_id)
    if path and path.is_file():
        data = load_yaml(path)
        return data if isinstance(data, dict) else None
    if plan_id == _DEFAULT_PLAN:
        legacy = _registry_dir(root) / "soc_schedule_4p.yaml"
        if legacy.is_file():
            data = load_yaml(legacy)
            if isinstance(data, dict):
                data.setdefault("plan_id", _DEFAULT_PLAN)
                return data
    return None


def _aliases_map(plan: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in plan.get("milestones") or []:
        if not isinstance(m, dict):
            continue
        mid = normalize_milestone_id(str(m.get("id", "")))
        if not mid:
            continue
        out[mid.lower()] = mid
        out[mid] = mid
        for alias in m.get("aliases") or []:
            out[normalize_milestone_id(str(alias)).lower()] = mid
    return out


def _ordered_from_plan(plan: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    items = [m for m in (plan.get("milestones") or []) if isinstance(m, dict)]
    items.sort(key=lambda x: int(x.get("order") or 0))
    ordered: list[str] = []
    labels: dict[str, str] = {}
    for m in items:
        mid = normalize_milestone_id(str(m.get("id", "")))
        if not mid:
            continue
        ordered.append(mid)
        labels[mid] = str(m.get("label_en") or m.get("label_ko") or m.get("label") or mid)
    return ordered, labels


def _ordered_from_state(state: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    ordered: list[str] = []
    labels: dict[str, str] = {}
    for m in state.get("milestones") or []:
        if not isinstance(m, dict):
            continue
        mid = normalize_milestone_id(str(m.get("id", "")))
        if not mid:
            continue
        ordered.append(mid)
        labels[mid] = str(m.get("label") or m.get("label_en") or m.get("label_ko") or mid)
    return ordered, labels


def resolve_canonical_id(milestone_id: str, ctx: ScheduleContext, plan: dict[str, Any] | None) -> str:
    mid = normalize_milestone_id(milestone_id)
    if mid in ctx.id_to_order:
        return mid
    if plan:
        aliases = _aliases_map(plan)
        canon = aliases.get(mid.lower())
        if canon:
            return canon
    return mid


def resolve_schedule_context(
    state: dict[str, Any],
    root: Path | None = None,
    *,
    config: dict[str, Any] | None = None,
) -> ScheduleContext:
    """Build ordered milestone ladder for a project."""
    plan_id = str(state.get("schedule_plan") or state.get("milestone_plan") or "")
    if not plan_id and root is not None:
        plan_id = default_plan_id(root, config)

    state_ordered, state_labels = _ordered_from_state(state)
    if state_ordered and (plan_id == "custom" or not plan_id):
        id_to_order = {m: i for i, m in enumerate(state_ordered)}
        return ScheduleContext(
            plan_id="custom",
            culture="custom",
            ordered_ids=state_ordered,
            id_to_order=id_to_order,
            labels=state_labels,
            source="state.yaml",
        )

    plan: dict[str, Any] | None = None
    if root is not None and plan_id and plan_id != "custom":
        plan = load_plan(root, plan_id)

    if plan:
        plan_ordered, plan_labels = _ordered_from_plan(plan)
        if state_ordered:
            merged = list(state_ordered)
            for mid in plan_ordered:
                if mid not in merged:
                    merged.append(mid)
            ordered = merged
            labels = {**plan_labels, **state_labels}
            source = "state.yaml+plan"
        else:
            ordered = plan_ordered
            labels = plan_labels
            source = "registry"
        culture = str(plan.get("culture") or "")
    elif state_ordered:
        ordered = state_ordered
        labels = state_labels
        culture = "custom"
        source = "state.yaml"
        plan_id = plan_id or "custom"
    else:
        ordered = ["M1", "M2", "M3", "M4"]
        labels = {m: m for m in ordered}
        culture = "semiconductor_dv"
        source = "legacy_default"
        plan_id = plan_id or _DEFAULT_PLAN

    aliases: dict[str, str] = _aliases_map(plan) if plan else {}
    id_to_order: dict[str, int] = {}
    for i, mid in enumerate(ordered):
        id_to_order[mid] = i
        id_to_order[mid.lower()] = i
        for alias, canon in aliases.items():
            if canon == mid:
                id_to_order[alias] = i

    return ScheduleContext(
        plan_id=plan_id,
        culture=culture,
        ordered_ids=ordered,
        id_to_order=id_to_order,
        labels=labels,
        source=source,
    )


def milestone_rank(milestone_id: str, ctx: ScheduleContext, plan: dict[str, Any] | None = None) -> int | None:
    mid = resolve_canonical_id(milestone_id, ctx, plan)
    rank = ctx.rank(mid)
    if rank is not None:
        return rank
    m = _LEGACY_M_RE.match(mid)
    if m and ctx.plan_id in (_DEFAULT_PLAN, "soc-dv-4p-v1", ""):
        num = int(m.group(1))
        return num - 1 if num >= 1 else None
    return None


def validate_project_schedule(
    root: Path,
    project_dir: Path,
    *,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Check state.yaml milestones vs plan and group manifests."""
    from soc_verify.models import load_yaml as ly

    state = ly(project_dir / "state.yaml") or {}
    ctx = resolve_schedule_context(state, root, config=config)
    plan = load_plan(root, ctx.plan_id) if ctx.plan_id != "custom" else None

    issues: list[str] = []
    current = normalize_milestone_id(str(state.get("current_milestone", "")))
    if current and milestone_rank(current, ctx, plan) is None:
        issues.append(f"current_milestone {current!r} not in plan {ctx.plan_id}")

    groups_checked: list[dict[str, Any]] = []
    ver_root = project_dir / "verification"
    if ver_root.is_dir():
        for stage_dir in ver_root.iterdir():
            if not stage_dir.is_dir():
                continue
            for group_dir in stage_dir.iterdir():
                if not group_dir.is_dir():
                    continue
                manifest_path = group_dir / "manifest.yaml"
                if not manifest_path.is_file():
                    continue
                manifest = ly(manifest_path) or {}
                gm = normalize_milestone_id(str(manifest.get("milestone", "")))
                gr = milestone_rank(gm, ctx, plan) if gm else None
                ok = gr is not None
                if not ok:
                    issues.append(f"{stage_dir.name}/{group_dir.name}: milestone {gm!r} unknown")
                groups_checked.append(
                    {
                        "stage": stage_dir.name,
                        "group": group_dir.name,
                        "milestone": gm,
                        "valid": ok,
                    }
                )

    return {
        "project_id": project_dir.name,
        "schedule": ctx.to_dict(),
        "current_milestone": current,
        "issues": issues,
        "valid": not issues,
        "groups_checked": groups_checked,
    }


def list_plans(root: Path) -> list[dict[str, Any]]:
    idx = load_plan_index(root)
    out: list[dict[str, Any]] = []
    for entry in idx.get("plans") or []:
        if not isinstance(entry, dict):
            continue
        pid = str(entry.get("id", ""))
        plan = load_plan(root, pid) if pid != "custom" else None
        milestone_ids = []
        if plan:
            milestone_ids, _ = _ordered_from_plan(plan)
        out.append(
            {
                "id": pid,
                "label_ko": entry.get("label_ko"),
                "label_en": entry.get("label_en"),
                "culture": entry.get("culture") or (plan or {}).get("culture"),
                "milestone_ids": milestone_ids,
                "custom": pid == "custom",
            }
        )
    return out