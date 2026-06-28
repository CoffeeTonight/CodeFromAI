"""LLM brief builder with ERL context injection for verify-group runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ops.self_harness import load_spec, retrieve_erl_context


def build_llm_brief(
    project_dir: Path,
    run_dir: Path,
    *,
    stage: str = "",
    group: str = "",
    node: str = "run_gate",
    graph: str = "verify_group",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build llm_brief.json index for company LLM — graph position + read order."""
    signals_path = run_dir / "improvement_signal.json"
    signals: dict[str, Any] = {}
    if signals_path.is_file():
        try:
            signals = json.loads(signals_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            signals = {}

    stage = stage or str(signals.get("stage") or "")
    group = group or str(signals.get("group") or "")

    payload: dict[str, Any] = {
        "contract": "llm_brief_v1",
        "source": "self_harness",
        "graph": graph,
        "node": node,
        "required": True,
        "run_id": run_dir.name,
        "project_id": project_dir.name,
        "stage": stage,
        "group": group,
        "read_order": [
            "graph_step.json",
            "md_only_prompt.json",
            "md_only_prompt.md",
        ],
        "write_artifacts": [
            f"verdict_{group}.json" if group else "verdict_*.json",
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


def inject_erl_into_llm_brief(
    brief: dict[str, Any],
    project_dir: Path,
    *,
    stage: str = "",
    group: str = "",
    error_kind: str = "",
    limit: int = 5,
) -> dict[str, Any]:
    """Inject tag-ranked ERL heuristics into llm_brief when spec allows."""
    root = project_dir.parent.parent
    spec = load_spec(root)
    erl_cfg = spec.get("erl") or {}
    if not erl_cfg.get("inject_into_llm_brief", True):
        return brief

    stage = stage or str(brief.get("stage") or "")
    group = group or str(brief.get("group") or "")
    error_kind = error_kind or str((brief.get("signals") or {}).get("error_kind") or "")

    heuristics = retrieve_erl_context(
        project_dir,
        stage=stage,
        group=group,
        error_kind=error_kind,
        limit=limit,
    )
    out = dict(brief)
    out["erl_context"] = {
        "inject": True,
        "stage": stage,
        "group": group,
        "error_kind": error_kind,
        "heuristics": heuristics,
        "count": len(heuristics),
    }
    if heuristics:
        out["read_order"] = list(out.get("read_order") or []) + [
            "knowledge/patterns/index.yaml",
        ]
        out["rules"] = list(out.get("rules") or []) + [
            "Consult erl_context.heuristics before retrying failed gates.",
        ]
    return out


def setup_group_injection(
    project_dir: Path,
    run_dir: Path,
    *,
    stage: str = "",
    group: str = "",
    error_kind: str = "",
    node: str = "run_gate",
    write: bool = True,
) -> dict[str, Any]:
    """Build llm_brief and inject ERL context; optionally write llm_brief.json."""
    brief = build_llm_brief(
        project_dir,
        run_dir,
        stage=stage,
        group=group,
        node=node,
    )
    signals_path = run_dir / "improvement_signal.json"
    if signals_path.is_file():
        try:
            brief["signals"] = json.loads(signals_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    error_kind = error_kind or str((brief.get("signals") or {}).get("error_kind") or "")
    brief = inject_erl_into_llm_brief(
        brief,
        project_dir,
        stage=stage or str(brief.get("stage") or ""),
        group=group or str(brief.get("group") or ""),
        error_kind=error_kind,
    )
    if write:
        path = run_dir / "llm_brief.json"
        path.write_text(json.dumps(brief, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return brief