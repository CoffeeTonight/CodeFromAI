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


def _project_has_weakness_ops(project_dir: Path) -> bool:
    return (project_dir / "ops" / "self_harness.py").is_file()


def _project_has_full_self_harness_ops(project_dir: Path) -> bool:
    """Full pipeline needs project erl_reflect + meta_collect alongside self_harness."""
    ops = project_dir / "ops"
    return (
        (ops / "self_harness.py").is_file()
        and (ops / "erl_reflect.py").is_file()
        and (ops / "meta_collect.py").is_file()
    )


def _resolve_weakness_miners(project_dir: Path):
    if _project_has_weakness_ops(project_dir):
        _ensure_project_ops(project_dir)
        from ops.self_harness import mine_weaknesses, write_weakness_report

        return mine_weaknesses, write_weakness_report
    from soc_verify.platform_self_harness import mine_weaknesses, write_weakness_report

    return mine_weaknesses, write_weakness_report


def integrate_training_finalize_weakness(
    root: Path,
    project_dir: Path,
    run_dir: Path,
    state: dict[str, Any],
) -> dict[str, Any]:
    """Write weakness_report on training finalize (meta_collect skipped)."""
    from soc_verify.improvement_eval import (
        build_snapshot,
        collect_run_signals,
        write_improvement_signal,
        write_improvement_snapshot,
    )

    state_dict = dict(state)
    signals = collect_run_signals(run_dir, state_dict)
    write_improvement_signal(run_dir, signals)
    snapshot = build_snapshot(project_dir, run_dir, signals, as_of=state_dict.get("as_of"))
    write_improvement_snapshot(run_dir, snapshot)

    mine_weaknesses, write_weakness_report = _resolve_weakness_miners(project_dir)
    report = mine_weaknesses(
        root,
        project_dir,
        run_dir,
        signals=signals,
        snapshot=snapshot.to_dict(),
    )
    path = write_weakness_report(run_dir, report)
    return {
        "ok": True,
        "weakness_count": len(report.get("weaknesses") or []),
        "weakness_report": str(path),
        "source": report.get("source", "project"),
    }


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
    if not _project_has_full_self_harness_ops(project_dir):
        return {
            "ok": True,
            "run_id": run_dir.name,
            "weakness_count": 0,
            "proposal_count": 0,
            "llm_patch_count": 0,
            "erl_heuristic": None,
            "llm_brief_written": False,
            "harness_llm_prompt_written": False,
            "erl_context_count": 0,
            "payload": meta_payload,
        }
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