"""Adaptive setup helpers — milestone context, LLM prompts, bootstrap validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from soc_verify.milestone_plans import load_plan, resolve_schedule_context
from soc_verify.models import load_yaml
from soc_verify.skill_registry import list_skills, load_registry
from soc_verify.setup_wizard import load_setup_state


def phase_tasks_for_plan(plan: dict[str, Any] | None) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    if not plan:
        return out
    for m in plan.get("milestones") or []:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("id", ""))
        tasks = m.get("phase_tasks") or []
        if mid and tasks:
            out[mid] = [str(t) for t in tasks]
    return out


def build_milestone_context(
    root: Path,
    project_dir: Path,
    *,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = load_yaml(project_dir / "state.yaml") or {}
    ctx = resolve_schedule_context(state, root, config=config)
    plan = load_plan(root, ctx.plan_id) if ctx.plan_id != "custom" else None
    phase_tasks = phase_tasks_for_plan(plan)

    milestones: list[dict[str, Any]] = []
    for mid in ctx.ordered_ids:
        item: dict[str, Any] = {
            "id": mid,
            "label": ctx.labels.get(mid, mid),
            "phase_tasks": phase_tasks.get(mid, []),
        }
        if plan:
            for pm in plan.get("milestones") or []:
                if isinstance(pm, dict) and str(pm.get("id")) == mid:
                    item["design_goal"] = pm.get("design_goal", "")
                    item["dv_focus"] = pm.get("dv_focus") or []
                    break
        milestones.append(item)

    current = str(state.get("current_milestone", ""))
    return {
        "project_id": project_dir.name,
        "schedule_plan": ctx.plan_id,
        "culture": ctx.culture,
        "current_milestone": current,
        "milestones": milestones,
        "phase_tasks_index": phase_tasks,
    }


def load_user_skillset(
    root: Path,
    project_dir: Path,
    *,
    state_override: dict[str, Any] | None = None,
) -> str:
    if state_override:
        text = state_override.get("user_skillset") or state_override.get("skillset_text")
        if text:
            return str(text).strip()
    setup = load_setup_state(root)
    answers = setup.get("answers") or {}
    for key in ("user_skillset", "skillset_text", "verification_skills"):
        if answers.get(key):
            return str(answers[key]).strip()
    intake = project_dir / "skills" / "intake.md"
    if intake.is_file():
        return intake.read_text(encoding="utf-8").strip()
    return ""


_GATE_MD_NAMES = ("CHECK.md", "RESPOND.md", "MILESTONE.md")
_GATE_META_NAMES = ("manifest.yaml",)


def _rel_project_path(project_dir: Path, path: Path) -> str:
    try:
        return str(path.relative_to(project_dir))
    except ValueError:
        return str(path)


def _verification_groups_for_milestone(
    project_dir: Path,
    milestone: str,
) -> list[dict[str, Any]]:
    """Gate folders under verification/ whose manifest milestone matches."""
    ver_root = project_dir / "verification"
    if not ver_root.is_dir():
        return []
    groups: list[dict[str, Any]] = []
    for manifest_path in sorted(ver_root.glob("*/*/manifest.yaml")):
        manifest = load_yaml(manifest_path) or {}
        gate_milestone = str(manifest.get("milestone") or "").strip()
        if milestone and gate_milestone and gate_milestone != milestone:
            continue
        group_dir = manifest_path.parent
        stage = group_dir.parent.name
        group = group_dir.name
        paths: dict[str, str] = {}
        for name in _GATE_MD_NAMES:
            p = group_dir / name
            if p.is_file():
                paths[name.replace(".md", "").lower()] = _rel_project_path(project_dir, p)
        if manifest_path.is_file():
            paths["manifest"] = _rel_project_path(project_dir, manifest_path)
        obsidian_base = project_dir / "knowledge" / "obsidian" / "02-stages" / stage / "groups" / group
        obsidian_paths: dict[str, str] = {}
        for name in _GATE_MD_NAMES:
            p = obsidian_base / name
            if p.is_file():
                obsidian_paths[name.replace(".md", "").lower()] = _rel_project_path(project_dir, p)
        groups.append(
            {
                "stage": stage,
                "group": group,
                "milestone": gate_milestone or milestone,
                "paths": paths,
                "obsidian_paths": obsidian_paths,
            }
        )
    return groups


def build_setup_read_catalog(
    project_dir: Path,
    *,
    milestone: str = "",
    run_dir: Path | None = None,
    materialized_groups: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Index of MD/YAML the setup LLM should read — current milestone scope only."""
    mid = milestone.strip()
    skill_entries: list[dict[str, Any]] = []
    for sk in list_skills(project_dir, milestone=mid):
        rel = str(sk.get("path") or "")
        skill_path = project_dir / rel if rel else None
        entry: dict[str, Any] = {
            "id": sk.get("id"),
            "name": sk.get("name"),
            "milestone_ids": sk.get("milestone_ids"),
            "methodology": sk.get("methodology"),
            "path": rel,
            "exists": bool(skill_path and skill_path.is_file()),
            "role": "methodology",
        }
        obsidian_skill = project_dir / "knowledge" / "obsidian" / "04-skills" / f"{sk.get('id')}.md"
        if obsidian_skill.is_file():
            entry["obsidian_path"] = _rel_project_path(project_dir, obsidian_skill)
        skill_entries.append(entry)

    verification = _verification_groups_for_milestone(project_dir, mid)
    if materialized_groups:
        seen = {(g["stage"], g["group"]) for g in verification}
        for mg in materialized_groups:
            if not mg.get("materialized"):
                continue
            stage = str(mg.get("stage", ""))
            group = str(mg.get("group", ""))
            if (stage, group) in seen:
                continue
            group_dir = project_dir / "verification" / stage / group
            paths = {
                name.replace(".md", "").lower(): _rel_project_path(project_dir, group_dir / name)
                for name in _GATE_MD_NAMES
                if (group_dir / name).is_file()
            }
            manifest = group_dir / "manifest.yaml"
            if manifest.is_file():
                paths["manifest"] = _rel_project_path(project_dir, manifest)
            verification.append(
                {
                    "stage": stage,
                    "group": group,
                    "milestone": str(mg.get("milestone") or mid),
                    "paths": paths,
                    "obsidian_paths": {},
                    "source": "materialize_verification",
                }
            )

    run_artifacts: list[str] = []
    if run_dir and run_dir.is_dir():
        for name in (
            "milestone_context.json",
            "materialize_verification.json",
            "skills_registered.json",
            "setup_adapt_prompt.json",
            "read_catalog.json",
        ):
            p = run_dir / name
            if p.is_file():
                run_artifacts.append(_rel_project_path(project_dir, p))

    intake = project_dir / "skills" / "intake.md"
    extras: list[dict[str, str]] = []
    if intake.is_file():
        extras.append({"role": "skill_intake", "path": _rel_project_path(project_dir, intake)})

    index_moc = project_dir / "knowledge" / "obsidian" / "00-index" / "PROJECT-MOC.md"
    if index_moc.is_file():
        extras.append({"role": "obsidian_index", "path": _rel_project_path(project_dir, index_moc)})

    return {
        "contract": "setup_read_catalog_v1",
        "milestone": mid,
        "instruction_ko": (
            "sandbox read_file로 아래 paths를 읽고 마일스톤에 맞는 가이드를 작성하세요. "
            "skills=방법론, verification=게이트 CHECK/RESPOND, obsidian=동일 내용 미러."
        ),
        "skills": skill_entries,
        "verification": verification,
        "extras": extras,
        "run_artifacts": run_artifacts,
        "read_order": [
            "milestone_context.json",
            "skills/*/SKILL.md (현재 마일스톤)",
            "verification/{stage}/{group}/CHECK.md",
            "verification/{stage}/{group}/RESPOND.md",
        ],
    }


def write_read_catalog_artifact(
    run_dir: Path,
    catalog: dict[str, Any],
) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "read_catalog.json"
    path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_milestone_context_artifact(run_dir: Path, context: dict[str, Any]) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "milestone_context.json"
    path.write_text(json.dumps(context, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_setup_adapt_prompt(
    run_dir: Path,
    *,
    context: dict[str, Any],
    skills: list[dict[str, Any]],
    registry: dict[str, Any],
    read_catalog: dict[str, Any] | None = None,
) -> Path:
    catalog = read_catalog or {}
    payload = {
        "task": "setup_adapt",
        "instruction": (
            "Read read_catalog paths (skills + verification MD) and milestone_context. "
            "Use sandbox read_file on catalog paths before writing setup_adapt.json. "
            "Write setup_adapt.json describing adaptive tools/scripts the project needs. "
            "Generate minimal Python helpers under projects/{id}/tools/ only when necessary."
        ),
        "milestone_context": context,
        "skills": skills,
        "skill_registry": registry,
        "read_catalog": catalog,
        "required_outputs": [
            "setup_adapt.json",
            "projects/{id}/tools/*.py (optional, milestone-scoped)",
        ],
    }
    path = run_dir / "setup_adapt_prompt.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_bootstrap_prompt(
    run_dir: Path,
    *,
    context: dict[str, Any],
    adapt: dict[str, Any],
    skills: list[dict[str, Any]],
    read_catalog: dict[str, Any] | None = None,
) -> Path:
    payload = {
        "task": "setup_bootstrap",
        "instruction": (
            "Read read_catalog verification CHECK/RESPOND and setup_adapt.json. "
            "Create beginner-friendly run scripts aligned with current-milestone gates. "
            "Must include projects/{id}/scripts/run_beginner.sh that sources env and "
            "runs the current-milestone smoke path. Write bootstrap_finalize.json when done."
        ),
        "milestone_context": context,
        "setup_adapt": adapt,
        "skills": skills,
        "read_catalog": read_catalog or {},
        "required_outputs": [
            "projects/{id}/scripts/run_beginner.sh",
            "projects/{id}/scripts/README.md (update if exists)",
            "bootstrap_finalize.json",
        ],
    }
    path = run_dir / "bootstrap_prompt.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def validate_setup_adapt(project_dir: Path, run_dir: Path) -> dict[str, Any]:
    issues: list[str] = []
    adapt_path = run_dir / "setup_adapt.json"
    if not adapt_path.is_file():
        issues.append("missing setup_adapt.json")
        return {"ok": False, "issues": issues}

    try:
        adapt = json.loads(adapt_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        issues.append("setup_adapt.json invalid JSON")
        return {"ok": False, "issues": issues}

    if not adapt.get("summary") and not adapt.get("tools"):
        issues.append("setup_adapt.json needs summary or tools")
    return {"ok": not issues, "issues": issues, "adapt": adapt}


def validate_bootstrap(project_dir: Path, run_dir: Path) -> dict[str, Any]:
    issues: list[str] = []
    fin = run_dir / "bootstrap_finalize.json"
    if not fin.is_file():
        issues.append("missing bootstrap_finalize.json")
    script = project_dir / "scripts" / "run_beginner.sh"
    if not script.is_file():
        issues.append("missing projects/{id}/scripts/run_beginner.sh")
    elif not script.read_text(encoding="utf-8").strip().startswith("#!"):
        issues.append("run_beginner.sh should start with shebang")
    return {"ok": not issues, "issues": issues}


def collect_skills_summary(
    project_dir: Path,
    *,
    milestone: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    registry = load_registry(project_dir)
    skills = list_skills(project_dir, milestone=milestone)
    slim = [
        {
            "id": s.get("id"),
            "name": s.get("name"),
            "milestone_ids": s.get("milestone_ids"),
            "methodology": s.get("methodology"),
            "tags": s.get("tags"),
            "path": s.get("path"),
        }
        for s in skills
    ]
    return slim, registry