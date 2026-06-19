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
) -> Path:
    payload = {
        "task": "setup_adapt",
        "instruction": (
            "Read milestone_context.json and registered skills. "
            "Write setup_adapt.json describing adaptive tools/scripts the project needs. "
            "Generate minimal Python helpers under projects/{id}/tools/ only when necessary."
        ),
        "milestone_context": context,
        "skills": skills,
        "skill_registry": registry,
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
) -> Path:
    payload = {
        "task": "setup_bootstrap",
        "instruction": (
            "Create beginner-friendly run scripts. "
            "Must include projects/{id}/scripts/run_beginner.sh that sources env and "
            "runs the current-milestone smoke path. Write bootstrap_finalize.json when done."
        ),
        "milestone_context": context,
        "setup_adapt": adapt,
        "skills": skills,
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


def collect_skills_summary(project_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    registry = load_registry(project_dir)
    skills = list_skills(project_dir)
    slim = [
        {
            "id": s.get("id"),
            "name": s.get("name"),
            "milestone_ids": s.get("milestone_ids"),
            "tags": s.get("tags"),
            "path": s.get("path"),
        }
        for s in skills
    ]
    return slim, registry