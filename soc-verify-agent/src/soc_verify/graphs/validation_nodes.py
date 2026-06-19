"""SoC validation autonomy nodes — item parse, judge, apply, item repro."""

from __future__ import annotations

from typing import Any

from soc_verify.config import load_user_config
from soc_verify.graph_step import append_graph_trace, write_graph_step
from soc_verify.node_gate import finalize_node_gate
from soc_verify.graphs.state import VerifyGroupState
from soc_verify.graphs.verify_helpers import project_dir, run_dir
from soc_verify.llm_runner import invoke_validation_judge
from soc_verify.validation_autonomy import (
    apply_validation_judgment,
    build_validation_judge_prompt,
    collect_validation_items,
    load_validation_judgment,
    run_pending_repro,
    write_validation_items,
)


def parse_validation_items_node(state: VerifyGroupState) -> dict[str, Any]:
    """SoC validation — extract goal/checklist items from CHECK.md + logs (not coverage)."""
    pd = project_dir(state)
    rd = run_dir(state)
    stage = state["stage"]
    group = state["group"]

    payload = collect_validation_items(pd, stage=stage, group=group, run_dir=rd)
    write_validation_items(rd, payload)

    write_graph_step(
        rd,
        graph="verify_group",
        node="parse_validation_items",
        group=group,
        stage=stage,
        runner=state.get("runner", "python"),
        fix_round=int(state.get("fix_round", 0)),
        orchestrator_run_id=state.get("orchestrator_run_id", ""),
        extra={
            "failing_count": payload.get("failing_count"),
            "needs_judgment": payload.get("needs_judgment"),
        },
    )
    append_graph_trace(
        rd,
        {
            "node": "parse_validation_items",
            "failing_count": payload.get("failing_count"),
            "needs_judgment": payload.get("needs_judgment"),
        },
    )
    root = pd.parent.parent
    finalize_node_gate(
        root,
        "verify_group",
        "parse_validation_items",
        state={**state, "validation_items": payload},
        run_dir=rd,
        summary_ko=f"validation items — failing={payload.get('failing_count', 0)}",
        evidence=[{"path": "runs/{}/validation_items.json".format(rd.name)}],
    )
    return {
        "validation_needs_judgment": bool(payload.get("needs_judgment")),
        "validation_items": payload,
    }


def validation_judge_node(state: VerifyGroupState) -> dict[str, Any]:
    """LLM judges per-item action: reproduce / narrow / exclude / continue_rest."""
    pd = project_dir(state)
    rd = run_dir(state)
    stage = state["stage"]
    group = state["group"]
    run_id = state["run_id"]
    items_payload = state.get("validation_items") or {}

    if not items_payload:
        items_payload = collect_validation_items(pd, stage=stage, group=group, run_dir=rd)

    prompt = build_validation_judge_prompt(
        project_dir=pd,
        stage=stage,
        group=group,
        run_id=run_id,
        items_payload=items_payload,
    )
    root = pd.parent.parent
    try:
        config = load_user_config(root)
    except FileNotFoundError:
        config = None

    invoke_validation_judge(rd, payload=prompt, root=root, config=config)
    judgment = load_validation_judgment(rd, items_payload)

    write_graph_step(
        rd,
        graph="verify_group",
        node="validation_judge",
        group=group,
        stage=stage,
        runner="llm",
        fix_round=int(state.get("fix_round", 0)),
        orchestrator_run_id=state.get("orchestrator_run_id", ""),
        extra={"sequence_action": judgment.get("sequence_action")},
    )
    append_graph_trace(
        rd,
        {"node": "validation_judge", "sequence_action": judgment.get("sequence_action")},
    )
    finalize_node_gate(
        root,
        "verify_group",
        "validation_judge",
        state={**state, "validation_judgment": judgment},
        run_dir=rd,
        summary_ko=str(judgment.get("verdict_summary_ko", "")),
        evidence=[{"path": f"runs/{run_id}/validation_judgment.json"}],
    )
    return {"validation_judgment": judgment}


def apply_validation_plan_node(state: VerifyGroupState) -> dict[str, Any]:
    """Apply judgment — narrow.md, excludes, item repro prompts."""
    pd = project_dir(state)
    rd = run_dir(state)
    stage = state["stage"]
    group = state["group"]
    items_payload = state.get("validation_items") or {}
    judgment = state.get("validation_judgment") or load_validation_judgment(rd, items_payload)

    result = apply_validation_judgment(
        pd,
        rd,
        judgment,
        stage=stage,
        group=group,
    )
    seq_action = str(judgment.get("sequence_action", "halt"))
    continue_rest = seq_action in ("continue_remaining", "partial_accept")

    questions: list[dict[str, Any]] = []
    if result.get("narrow_md"):
        questions.append(
            {
                "id": f"Q-val-narrow-{state['run_id']}",
                "type": "validation",
                "context": f"{stage}/{group}",
                "question": judgment.get("verdict_summary_ko", "validation narrow — see validation_narrow.md"),
                "blocking": "no",
                "artifact": result.get("narrow_md"),
            }
        )

    write_graph_step(
        rd,
        graph="verify_group",
        node="apply_validation_plan",
        group=group,
        stage=stage,
        runner=state.get("runner", "python"),
        fix_round=int(state.get("fix_round", 0)),
        orchestrator_run_id=state.get("orchestrator_run_id", ""),
        extra=result,
    )
    append_graph_trace(rd, {"node": "apply_validation_plan", **result})

    root = pd.parent.parent
    finalize_node_gate(
        root,
        "verify_group",
        "apply_validation_plan",
        state={**state, "validation_sequence_action": seq_action},
        run_dir=rd,
        summary_ko=str(judgment.get("verdict_summary_ko", "")),
        evidence=[{"path": f"runs/{state['run_id']}/validation_narrow.md"}],
    )
    return {
        "validation_sequence_action": seq_action,
        "validation_continue": continue_rest,
        "questions": questions,
    }


def run_pending_repro_node(state: VerifyGroupState) -> dict[str, Any]:
    """Sandbox item repro — run scripts/repro_*.sh for pending_repro entries only."""
    pd = project_dir(state)
    rd = run_dir(state)
    stage = state["stage"]
    group = state["group"]
    run_id = state["run_id"]

    result = run_pending_repro(
        pd,
        rd,
        stage=stage,
        group=group,
        run_id=run_id,
    )

    write_graph_step(
        rd,
        graph="verify_group",
        node="run_pending_repro",
        group=group,
        stage=stage,
        runner=state.get("runner", "python"),
        fix_round=int(state.get("fix_round", 0)),
        orchestrator_run_id=state.get("orchestrator_run_id", ""),
        extra={
            "pending_count": result.get("pending_count"),
            "executed_count": result.get("executed_count"),
        },
    )
    append_graph_trace(rd, {"node": "run_pending_repro", **result})

    root = pd.parent.parent
    finalize_node_gate(
        root,
        "verify_group",
        "run_pending_repro",
        state=state,
        run_dir=rd,
        summary_ko=f"item repro — executed={result.get('executed_count', 0)}/{result.get('pending_count', 0)}",
        evidence=[{"path": f"runs/{run_id}/validation_repro_results.json"}],
    )
    return {"validation_repro_results": result}