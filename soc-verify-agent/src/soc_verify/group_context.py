"""Load user MD + manifest into structured context for graph nodes and LLM brief."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from soc_verify.models import load_yaml


def _read_md(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def load_group_context(group_dir: Path) -> dict[str, Any]:
    manifest = load_yaml(group_dir / "manifest.yaml")
    group_name = str(manifest.get("group", group_dir.name))
    spec_path = group_dir / f"{group_name}.md"
    return {
        "stage": manifest.get("stage", ""),
        "group": group_name,
        "manifest": manifest,
        "check_md": _read_md(group_dir / "CHECK.md"),
        "respond_md": _read_md(group_dir / "RESPOND.md"),
        "milestone_md": _read_md(group_dir / "MILESTONE.md"),
        "run_md": _read_md(group_dir / "RUN.md"),
        "spec_md": _read_md(spec_path),
        "spec_md_path": str(spec_path.name) if spec_path.is_file() else "",
        "group_dir": str(group_dir.resolve()),
    }


def llm_brief_payload(
    *,
    graph: str,
    node: str,
    group_context: dict[str, Any],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Index for company LLM — read MD from md_only_prompt.* ; position from graph_step.json."""
    payload: dict[str, Any] = {
        "source": "langgraph",
        "graph": graph,
        "node": node,
        "required": True,
        "group": group_context.get("group"),
        "stage": group_context.get("stage"),
        "read_order": [
            "graph_step.json",
            "md_only_prompt.json",
            "md_only_prompt.md",
        ],
        "write_artifacts": [
            f"verdict_{group_context.get('group')}.json",
            "sub_stop.json",
        ],
        "on_success_promote": [
            "promote_decision.md",
            "crystallize_proposal.md",
        ],
        "rules": [
            "Verification logic: user MD only (md_only_prompt.md)",
            "Workflow position: graph_step.json (LangGraph)",
            "Do not report PASS without verdict_*.json",
        ],
    }
    if extra:
        payload.update(extra)
    return payload