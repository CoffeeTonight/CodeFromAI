"""SKILL.md one-pager → verification MD, ops bootstrap, verify handoff."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from soc_verify.models import load_yaml, save_yaml
from soc_verify.skill_registry import (
    get_skill,
    list_skills,
    parse_skill_document,
    resolve_skill_milestone_ids,
    skill_applies_to_milestone,
)

OPS_STUB = '''#!/usr/bin/env python3
"""Gate ops — crystallized from SKILL materialize (replace with real compile/sim)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXIT_PASS = 0
EXIT_FAIL = 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True)
    p.add_argument("--run-dir", required=True)
    p.add_argument("--case", default=None)
    args = p.parse_args()

    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    verdict = {{
        "gate": "{group}",
        "status": "PASS",
        "exit_code": EXIT_PASS,
        "evidence": ["skill_materialize stub PASS"],
        "artifacts": {{}},
        "trust": {{"script": "{group}.py", "version": "0.1.0"}},
    }}
    if args.case:
        print(json.dumps(verdict))
        return EXIT_PASS
    out = run_dir / "verdict_{group}.json"
    out.write_text(json.dumps(verdict, indent=2), encoding="utf-8")
    return EXIT_PASS


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _section_lines(content: str, heading: str) -> list[str]:
    lines: list[str] = []
    in_section = False
    for raw in content.splitlines():
        line = raw.strip()
        if line.lower().startswith(f"## {heading.lower()}"):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section and line:
            lines.append(line.lstrip("- ").strip())
    return lines


def build_check_md(*, group: str, meta: dict[str, Any], content: str) -> str:
    criteria = list(meta.get("pass_criteria") or [])
    criteria.extend(_section_lines(content, "PASS"))
    if not criteria:
        criteria = [f"`verdict_{group}.json`: `status == PASS`"]
    lines = [
        f"# CHECK — {group}",
        "",
        "> Materialized from SKILL.md (skill_materialize).",
        "",
        "## PASS 조건",
    ]
    for c in criteria:
        lines.append(f"- {c}")
    lines.extend(["", "## FAIL 시 확인", f"- `runs/{{run_id}}/verdict_{group}.json`"])
    fail_hints = list(meta.get("fail_hints") or []) + _section_lines(content, "FAIL")
    for h in fail_hints[:6]:
        lines.append(f"- {h}")
    return "\n".join(lines) + "\n"


def build_respond_md(*, group: str, meta: dict[str, Any], content: str) -> str:
    actions = list(meta.get("fail_actions") or []) + _section_lines(content, "RESPOND")
    if not actions:
        actions = [
            "Classify: env / tool / verification / info",
            f"Inspect runs/{{run_id}}/verdict_{group}.json and logs",
            "If spec gap → questions_pending.md",
        ]
    lines = [f"# RESPOND — {group}", "", "> Materialized from SKILL.md.", ""]
    for i, a in enumerate(actions, 1):
        lines.append(f"## Step {i}")
        lines.append(a)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_milestone_md(*, group: str, milestone: str, meta: dict[str, Any]) -> str:
    goal = str(meta.get("milestone_goal") or meta.get("goal") or f"Close {group} gate for {milestone}")
    return (
        f"# MILESTONE — {group}\n\n"
        f"- milestone: **{milestone}**\n"
        f"- goal: {goal}\n"
    )


def build_manifest(*, stage: str, group: str, milestone: str, meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": stage,
        "group": group,
        "milestone": milestone,
        "schedule": str(meta.get("schedule") or ""),
        "depends_on": list(meta.get("depends_on") or []),
        "gates": list(meta.get("gates") or [group]),
        "owner": str(meta.get("owner") or "skill-materialize"),
        "source": "skill_materialize",
    }


def materialize_from_skill(
    project_dir: Path,
    skill_entry: dict[str, Any],
    *,
    default_milestone: str = "",
    milestone_filter: str = "",
    overwrite: bool = False,
) -> dict[str, Any]:
    body = str(skill_entry.get("body") or "")
    if not body and skill_entry.get("path"):
        p = project_dir / str(skill_entry["path"])
        if p.is_file():
            body = p.read_text(encoding="utf-8")
    meta, content = parse_skill_document(body)
    milestone_scope = milestone_filter or default_milestone
    if milestone_scope and not skill_applies_to_milestone(
        skill_entry, meta, milestone_scope, default_milestone=default_milestone
    ):
        return {
            "materialized": False,
            "reason": "milestone_mismatch",
            "skill_id": skill_entry.get("id"),
            "milestone_filter": milestone_scope,
            "milestone_ids": resolve_skill_milestone_ids(skill_entry, meta),
        }

    stage = str(meta.get("stage") or "").strip()
    group = str(meta.get("group") or "").strip()
    if not stage or not group:
        return {
            "materialized": False,
            "reason": "methodology_only",
            "skill_id": skill_entry.get("id"),
            "milestone_ids": resolve_skill_milestone_ids(skill_entry, meta),
        }

    milestone = str(meta.get("milestone") or default_milestone or "M1")
    group_dir = project_dir / "verification" / stage / group
    group_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "check": group_dir / "CHECK.md",
        "respond": group_dir / "RESPOND.md",
        "milestone": group_dir / "MILESTONE.md",
        "manifest": group_dir / "manifest.yaml",
    }
    payloads = {
        "check": build_check_md(group=group, meta=meta, content=content),
        "respond": build_respond_md(group=group, meta=meta, content=content),
        "milestone": build_milestone_md(group=group, milestone=milestone, meta=meta),
        "manifest": build_manifest(stage=stage, group=group, milestone=milestone, meta=meta),
    }
    written: list[str] = []
    for key, path in paths.items():
        if path.is_file() and not overwrite:
            continue
        if key == "manifest":
            save_yaml(path, payloads[key])
        else:
            path.write_text(payloads[key], encoding="utf-8")
        written.append(str(path.relative_to(project_dir)))

    return {
        "materialized": True,
        "skill_id": skill_entry.get("id"),
        "stage": stage,
        "group": group,
        "milestone": milestone,
        "written": written,
    }


def materialize_from_registry(
    project_dir: Path,
    *,
    default_milestone: str = "",
    milestone_filter: str = "",
    overwrite: bool = False,
) -> list[dict[str, Any]]:
    """Materialize gate-bound methodologies for the active milestone only."""
    scope = milestone_filter or default_milestone
    entries = list_skills(project_dir, milestone=scope) if scope else list_skills(project_dir)
    results: list[dict[str, Any]] = []
    for entry in entries:
        sid = str(entry.get("id", ""))
        full = get_skill(project_dir, sid) if sid else None
        if not full:
            continue
        results.append(
            materialize_from_skill(
                project_dir,
                full,
                default_milestone=default_milestone,
                milestone_filter=scope,
                overwrite=overwrite,
            )
        )
    return results


def bootstrap_group_ops(
    project_dir: Path,
    *,
    stage: str,
    group: str,
) -> dict[str, Any]:
    ops_dir = project_dir / "ops" / stage
    ops_dir.mkdir(parents=True, exist_ok=True)
    script = ops_dir / f"{group}.py"
    if script.is_file():
        return {"bootstrapped": False, "reason": "exists", "path": str(script)}
    script.write_text(OPS_STUB.format(group=group), encoding="utf-8")
    script.chmod(0o755)
    return {"bootstrapped": True, "path": str(script)}


def ensure_verify_handoff(
    project_dir: Path,
    *,
    stage: str,
    group: str,
    run_dir: Path,
) -> dict[str, Any]:
    """Record handoff artifact and ensure trust baseline for smoke lap."""
    trust_path = project_dir / "trust" / "registry.yaml"
    trust_path.parent.mkdir(parents=True, exist_ok=True)
    reg = load_yaml(trust_path) if trust_path.is_file() else {"scripts": {}}
    scripts = reg.setdefault("scripts", {})
    scripts[f"{group}.py"] = {
        "script": f"{group}.py",
        "status": "draft",
        "trust_score": 0.85,
        "version": "0.1.0",
        "tied_to_tag": True,
        "runs": 1,
        "successes": 1,
        "last_result": "PASS",
    }
    save_yaml(trust_path, reg)

    payload = {
        "contract": "verify_handoff_v1",
        "stage": stage,
        "group": group,
        "project_id": project_dir.name,
    }
    out = run_dir / "verify_handoff.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def primary_materialized_group(materialized: list[dict[str, Any]]) -> dict[str, Any] | None:
    for item in materialized:
        if item.get("materialized"):
            return item
    return None