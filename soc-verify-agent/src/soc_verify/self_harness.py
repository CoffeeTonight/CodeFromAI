"""Self-harness integration — wire project ops into verify_group meta_collect."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def _ensure_project_ops(project_dir: Path) -> None:
    project_str = str(project_dir)
    if project_str not in sys.path:
        sys.path.insert(0, project_str)


def run_self_harness_artifacts(
    root: Path,
    project_dir: Path,
    run_dir: Path,
    *,
    signals: dict[str, Any],
    snapshot: dict[str, Any],
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Mine → propose → LLM patches → ERL → llm_brief (no meta_collect_prompt write)."""
    _ensure_project_ops(project_dir)
    from ops.erl_reflect import write_erl_heuristic
    from ops.llm_brief import setup_group_injection
    from ops.self_harness import (
        mine_weaknesses,
        propose_harness_edits,
        propose_llm_skill_patches,
        write_harness_llm_prompt,
        write_weakness_report,
    )

    weakness_report = mine_weaknesses(
        root, project_dir, run_dir, signals=signals, snapshot=snapshot
    )
    write_weakness_report(run_dir, weakness_report)

    harness_proposal = propose_harness_edits(
        root, project_dir, run_dir, weakness_report=weakness_report
    )
    harness_proposal_llm = propose_llm_skill_patches(
        root, project_dir, run_dir, weakness_report=weakness_report
    )
    write_harness_llm_prompt(
        root, project_dir, run_dir, weakness_report=weakness_report
    )

    erl_path = write_erl_heuristic(
        project_dir,
        run_dir,
        signals=signals,
        snapshot=snapshot,
        weakness_report=weakness_report,
    )

    stage = str(weakness_report.get("stage") or signals.get("stage") or "")
    group = str(weakness_report.get("group") or signals.get("group") or "")
    error_kind = str(signals.get("error_kind") or "")

    setup_group_injection(
        project_dir,
        run_dir,
        stage=stage,
        group=group,
        error_kind=error_kind,
        node="meta_collect",
    )

    from ops.meta_collect import build_meta_collect_payload

    harness_payload = build_meta_collect_payload(
        root=root,
        project_dir=project_dir,
        run_dir=run_dir,
        signals=signals,
        snapshot=snapshot,
        state=state,
    )

    return {
        "weakness_count": len(weakness_report.get("weaknesses") or []),
        "proposal_count": len(harness_proposal.get("proposals") or []),
        "llm_patch_count": len(harness_proposal_llm.get("patches") or []),
        "erl_heuristic": str(erl_path) if erl_path else None,
        "llm_brief_written": (run_dir / "llm_brief.json").is_file(),
        "harness_llm_prompt_written": (run_dir / "harness_llm_prompt.json").is_file(),
        "payload": harness_payload,
    }


def merge_meta_collect_payloads(
    meta_payload: dict[str, Any],
    harness_payload: dict[str, Any],
) -> dict[str, Any]:
    """Combine meta_graph KPI payload with self-harness artifacts."""
    merged = dict(meta_payload)
    for key in (
        "weakness_report",
        "harness_proposal",
        "harness_proposal_llm",
        "erl_context",
        "self_harness_hints",
        "artifacts",
    ):
        if key in harness_payload:
            merged[key] = harness_payload[key]

    merged["self_harness"] = True
    merged["collected_at"] = harness_payload.get("collected_at") or meta_payload.get("collected_at")

    meta_instr = str(meta_payload.get("instruction") or "")
    harness_instr = str(harness_payload.get("instruction") or "")
    if harness_instr and harness_instr not in meta_instr:
        merged["instruction"] = f"{meta_instr} {harness_instr}".strip()

    return merged


def integrate_meta_collect(
    root: Path,
    project_dir: Path,
    run_dir: Path,
    *,
    meta_payload: dict[str, Any],
    signals: dict[str, Any],
    snapshot: dict[str, Any],
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run self-harness artifacts and merge into meta_graph meta_collect payload."""
    harness = run_self_harness_artifacts(
        root,
        project_dir,
        run_dir,
        signals=signals,
        snapshot=snapshot,
        state=state,
    )
    merged = merge_meta_collect_payloads(meta_payload, harness["payload"])
    return {
        "ok": True,
        "run_id": run_dir.name,
        "weakness_count": harness["weakness_count"],
        "proposal_count": harness["proposal_count"],
        "llm_patch_count": harness["llm_patch_count"],
        "erl_heuristic": harness["erl_heuristic"],
        "llm_brief_written": harness["llm_brief_written"],
        "harness_llm_prompt_written": harness["harness_llm_prompt_written"],
        "erl_context_count": len(merged.get("erl_context") or []),
        "payload": merged,
    }