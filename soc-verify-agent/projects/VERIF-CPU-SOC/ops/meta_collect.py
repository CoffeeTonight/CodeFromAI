"""Self-harness meta_collect — mine/propose/ERL integration for post-gate improvement loop."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ops.erl_reflect import write_erl_heuristic
from ops.llm_brief import setup_group_injection
from ops.self_harness import (
    load_weakness_report,
    mine_weaknesses,
    propose_harness_edits,
    propose_llm_skill_patches,
    retrieve_erl_context,
    write_harness_llm_prompt,
    write_weakness_report,
)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _read_graph_trace_nodes(run_dir: Path) -> list[str]:
    trace_path = run_dir / "graph_trace.jsonl"
    nodes: list[str] = []
    if not trace_path.is_file():
        return nodes
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            nodes.append(str(row.get("node", "")))
    return nodes


def build_meta_collect_payload(
    *,
    root: Path,
    project_dir: Path,
    run_dir: Path,
    signals: dict[str, Any] | None = None,
    snapshot: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble meta_collect prompt with self-harness artifacts and ERL context."""
    signals = dict(signals or _load_json(run_dir / "improvement_signal.json"))
    snapshot = dict(snapshot or _load_json(run_dir / "improvement_snapshot.json"))
    state = dict(state or {})

    stage = str(signals.get("stage") or snapshot.get("stage") or state.get("stage") or "")
    group = str(signals.get("group") or snapshot.get("group") or state.get("group") or "")
    error_kind = str(signals.get("error_kind") or "")

    weakness_report = load_weakness_report(run_dir)
    harness_proposal = _load_json(run_dir / "harness_proposal.json")
    harness_proposal_llm = _load_json(run_dir / "harness_proposal_llm.json")
    erl_context = retrieve_erl_context(
        project_dir,
        stage=stage,
        group=group,
        error_kind=error_kind,
    )

    self_harness_hints: list[dict[str, Any]] = []
    for w in weakness_report.get("weaknesses") or []:
        if not isinstance(w, dict):
            continue
        self_harness_hints.append(
            {
                "category": w.get("category"),
                "summary": w.get("summary"),
                "severity": w.get("severity", "medium"),
            }
        )

    return {
        "contract": "meta_collect_v1",
        "self_harness": True,
        "run_id": run_dir.name,
        "project_id": project_dir.name,
        "stage": stage,
        "group": group,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "improvement_signal": signals,
        "improvement_snapshot": snapshot,
        "graph_trace_nodes": _read_graph_trace_nodes(run_dir),
        "weakness_report": weakness_report,
        "harness_proposal": harness_proposal,
        "harness_proposal_llm": harness_proposal_llm,
        "erl_context": erl_context,
        "self_harness_hints": self_harness_hints,
        "artifacts": {
            "weakness_report": str(run_dir / "weakness_report.json"),
            "harness_proposal": str(run_dir / "harness_proposal.json"),
            "harness_proposal_llm": str(run_dir / "harness_proposal_llm.json"),
            "harness_llm_prompt": str(run_dir / "harness_llm_prompt.json"),
            "llm_brief": str(run_dir / "llm_brief.json"),
            "erl_patterns": str(project_dir / "knowledge" / "patterns"),
        },
        "instruction": (
            "Self-harness meta_collect: review weakness_report and harness proposals. "
            "Apply skill/graph patches only after pytest + held-out reverify. "
            "ERL heuristics are retrieval context — never auto-apply without human gate."
        ),
    }


def write_meta_collect_prompt(run_dir: Path, payload: dict[str, Any]) -> Path:
    path = run_dir / "meta_collect_prompt.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def run_meta_collect(
    root: Path,
    project_dir: Path,
    run_dir: Path,
    *,
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Full self-harness meta_collect pipeline: mine → propose → ERL → brief → prompt."""
    signals = _load_json(run_dir / "improvement_signal.json")
    snapshot = _load_json(run_dir / "improvement_snapshot.json")

    weakness_report = mine_weaknesses(root, project_dir, run_dir, signals=signals, snapshot=snapshot)
    write_weakness_report(run_dir, weakness_report)

    harness_proposal = propose_harness_edits(
        root, project_dir, run_dir, weakness_report=weakness_report
    )
    harness_proposal_llm = propose_llm_skill_patches(
        root, project_dir, run_dir, weakness_report=weakness_report
    )
    write_harness_llm_prompt(root, project_dir, run_dir, weakness_report=weakness_report)

    erl_path = write_erl_heuristic(
        project_dir,
        run_dir,
        signals=signals,
        snapshot=snapshot,
        weakness_report=weakness_report,
    )

    stage = str(weakness_report.get("stage") or "")
    group = str(weakness_report.get("group") or "")
    error_kind = str(signals.get("error_kind") or "")

    llm_brief = setup_group_injection(
        project_dir,
        run_dir,
        stage=stage,
        group=group,
        error_kind=error_kind,
        node="meta_collect",
    )

    payload = build_meta_collect_payload(
        root=root,
        project_dir=project_dir,
        run_dir=run_dir,
        signals=signals,
        snapshot=snapshot,
        state=state,
    )
    write_meta_collect_prompt(run_dir, payload)

    return {
        "ok": True,
        "run_id": run_dir.name,
        "weakness_count": len(weakness_report.get("weaknesses") or []),
        "proposal_count": len(harness_proposal.get("proposals") or []),
        "llm_patch_count": len(harness_proposal_llm.get("patches") or []),
        "erl_heuristic": str(erl_path) if erl_path else None,
        "llm_brief_written": (run_dir / "llm_brief.json").is_file(),
        "meta_collect_prompt": str(run_dir / "meta_collect_prompt.json"),
        "erl_context_count": len(payload.get("erl_context") or []),
    }