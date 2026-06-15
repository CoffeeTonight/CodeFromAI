"""MD-only prompts for company LLM — user verification MD separated from graph machinery."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_md_only_payload(group_context: dict[str, Any]) -> dict[str, Any]:
    """Payload the company LLM is allowed to use for verification logic."""
    out: dict[str, Any] = {
        "contract": "md_only",
        "group": group_context.get("group"),
        "stage": group_context.get("stage"),
        "check_md": group_context.get("check_md", ""),
        "respond_md": group_context.get("respond_md", ""),
        "milestone_md": group_context.get("milestone_md", ""),
        "run_md": group_context.get("run_md", ""),
    }
    if group_context.get("spec_md"):
        out["spec_md"] = group_context["spec_md"]
        out["spec_md_path"] = group_context.get("spec_md_path", "")
    return out


def build_md_only_user_message(payload: dict[str, Any]) -> str:
    parts = [
        f"# Verification group: {payload.get('group')} ({payload.get('stage')})",
        "",
        "## CHECK.md",
        payload.get("check_md") or "(empty)",
        "",
        "## RESPOND.md",
        payload.get("respond_md") or "(empty)",
        "",
        "## MILESTONE.md",
        payload.get("milestone_md") or "(empty)",
    ]
    if payload.get("run_md"):
        parts.extend(["", "## RUN.md", payload["run_md"]])
    spec_path = payload.get("spec_md_path") or ""
    if payload.get("spec_md"):
        parts.extend(["", f"## {spec_path or 'spec.md'}", payload["spec_md"]])
    return "\n".join(parts)


def write_md_only_prompt(run_dir: Path, group_context: dict[str, Any]) -> Path:
    payload = build_md_only_payload(group_context)
    path = run_dir / "md_only_prompt.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    (run_dir / "md_only_prompt.md").write_text(
        build_md_only_user_message(payload),
        encoding="utf-8",
    )
    return path


def build_promote_prompt(
    *,
    script_name: str,
    trust_report: dict[str, Any],
) -> dict[str, Any]:
    return {
        "contract": "promote_decision",
        "script": script_name,
        "trust_score": trust_report.get("trust_score"),
        "reproducibility": trust_report.get("reproducibility"),
        "golden_match": trust_report.get("golden_match"),
        "eligible_for_promote": trust_report.get("eligible_for_promote"),
        "evidence": trust_report.get("evidence", []),
    }


def write_promote_prompt(run_dir: Path, payload: dict[str, Any]) -> Path:
    path = run_dir / "promote_prompt.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path