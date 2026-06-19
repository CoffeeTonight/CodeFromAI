"""LangGraph meta_innovation_loop — main-LLM autonomous intervention."""

from __future__ import annotations

import json
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from soc_verify.graph_step import append_graph_trace
from soc_verify.graphs.meta_innovation_state import MetaInnovationState
from soc_verify.meta_innovation_loop import (
    append_mil_history,
    build_consensus_decision,
    build_beci_assessment,
    collect_observations_payload,
    load_mil_spec,
    validate_paper_data_update,
    validate_reviews,
    write_multi_llm_review_prompt,
    write_paper_data_prompt,
    write_skill_to_obsidian_prompt,
    write_subagent_verify_prompt,
)
from soc_verify.platform_telemetry import ensure_platform_baseline
from soc_verify.schedule_triggers import mark_trigger_run
from soc_verify.skill_registry import list_skills


_MIL_NODES = [
    "setup",
    "collect_observations",
    "beci_assess",
    "skill_to_obsidian",
    "subagent_verify",
    "multi_llm_review",
    "consensus_decide",
    "dispatch_intervention",
    "paper_data_maintain",
    "finalize",
]


def _root(state: MetaInnovationState) -> Path:
    return Path(state["root"])


def _project_dir(state: MetaInnovationState) -> Path:
    return Path(state["project_dir"])


def _run_dir(state: MetaInnovationState) -> Path:
    return _project_dir(state) / "runs" / "meta_innovation" / state["run_id"]


def setup(state: MetaInnovationState) -> dict[str, Any]:
    root = _root(state)
    run_id = state.get("run_id") or uuid.uuid4().hex[:12]
    as_of = state.get("as_of") or date.today().isoformat()
    run_dir = _project_dir(state) / "runs" / "meta_innovation" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    ensure_platform_baseline(root, trigger="meta_innovation_setup")
    append_graph_trace(run_dir, {"node": "setup", "graph": "meta_innovation_loop"})
    return {"run_id": run_id, "as_of": as_of, "events": {"setup": "ok"}}


def collect_observations(state: MetaInnovationState) -> dict[str, Any]:
    root = _root(state)
    project_dir = _project_dir(state)
    run_dir = _run_dir(state)
    obs = collect_observations_payload(root, project_dir)
    (run_dir / "observations.json").write_text(
        json.dumps(obs, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    append_graph_trace(run_dir, {"node": "collect_observations", "graph": "meta_innovation_loop"})
    return {"observations": obs, "events": {"collect_observations": "ok"}}


def beci_assess(state: MetaInnovationState) -> dict[str, Any]:
    root = _root(state)
    run_dir = _run_dir(state)
    obs = state.get("observations") or json.loads((run_dir / "observations.json").read_text(encoding="utf-8"))
    assessment = build_beci_assessment(root, obs)
    (run_dir / "beci_assessment.json").write_text(
        json.dumps(assessment, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    append_graph_trace(run_dir, {"node": "beci_assess", "graph": "meta_innovation_loop"})
    return {"beci_assessment": assessment, "events": {"beci_assess": len(assessment.get("intervention_targets", []))}}


def skill_to_obsidian(state: MetaInnovationState) -> dict[str, Any]:
    project_dir = _project_dir(state)
    run_dir = _run_dir(state)
    skills = list_skills(project_dir)
    write_skill_to_obsidian_prompt(run_dir, project_dir, skills)
    manifest = run_dir / "skill_obsidian_manifest.json"
    if not manifest.is_file():
        manifest.write_text(
            json.dumps({"converted": [], "status": "pending_llm"}, indent=2),
            encoding="utf-8",
        )
    return {"events": {"skill_to_obsidian": "prompt_ready"}}


def subagent_verify(state: MetaInnovationState) -> dict[str, Any]:
    project_dir = _project_dir(state)
    run_dir = _run_dir(state)
    assessment = state.get("beci_assessment") or {}
    if not assessment and (run_dir / "beci_assessment.json").is_file():
        assessment = json.loads((run_dir / "beci_assessment.json").read_text(encoding="utf-8"))
    skills = list_skills(project_dir)
    write_subagent_verify_prompt(run_dir, assessment=assessment, skills=skills)
    verify_path = run_dir / "subagent_verify.json"
    if not verify_path.is_file():
        verify_path.write_text(
            json.dumps({"status": "pending_llm", "ops_written": []}, indent=2),
            encoding="utf-8",
        )
    return {"events": {"subagent_verify": "prompt_ready"}}


def multi_llm_review(state: MetaInnovationState) -> dict[str, Any]:
    root = _root(state)
    run_dir = _run_dir(state)
    assessment = state.get("beci_assessment") or {}
    if not assessment and (run_dir / "beci_assessment.json").is_file():
        assessment = json.loads((run_dir / "beci_assessment.json").read_text(encoding="utf-8"))
    write_multi_llm_review_prompt(run_dir, assessment, root=root)
    return {"events": {"multi_llm_review": "prompt_ready"}}


def consensus_decide(state: MetaInnovationState) -> dict[str, Any]:
    root = _root(state)
    run_dir = _run_dir(state)
    spec = load_mil_spec(root)
    min_reviews = int(spec.get("min_llm_reviews", 3))
    review_result = validate_reviews(run_dir, min_reviews=min_reviews)
    assessment = state.get("beci_assessment") or json.loads(
        (run_dir / "beci_assessment.json").read_text(encoding="utf-8")
    )
    decision = {}
    if review_result["ok"]:
        decision = build_consensus_decision(run_dir, review_result, assessment)
    return {
        "review_result": review_result,
        "decision": decision,
        "consensus_ok": review_result["ok"],
        "events": {"consensus_decide": review_result.get("consensus", {})},
    }


def dispatch_intervention(state: MetaInnovationState) -> dict[str, Any]:
    run_dir = _run_dir(state)
    decision = state.get("decision") or {}
    if not decision and (run_dir / "meta_innovation_decision.json").is_file():
        decision = json.loads((run_dir / "meta_innovation_decision.json").read_text(encoding="utf-8"))
    dispatch = {
        "intervene": decision.get("intervene", False),
        "dispatch": decision.get("dispatch", []),
        "status": "queued" if decision.get("intervene") else "no_action",
    }
    (run_dir / "dispatch_intervention.json").write_text(
        json.dumps(dispatch, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return {"events": {"dispatch_intervention": dispatch}}


def paper_data_maintain(state: MetaInnovationState) -> dict[str, Any]:
    root = _root(state)
    project_dir = _project_dir(state)
    run_dir = _run_dir(state)
    decision = state.get("decision") or {}
    if not decision and (run_dir / "meta_innovation_decision.json").is_file():
        decision = json.loads((run_dir / "meta_innovation_decision.json").read_text(encoding="utf-8"))
    write_paper_data_prompt(run_dir, project_dir, decision, root=root)
    if not (run_dir / "paper_data_update.json").is_file():
        (run_dir / "paper_data_update.json").write_text(
            json.dumps({"status": "pending_llm", "campaigns_updated": []}, indent=2),
            encoding="utf-8",
        )
    return {"events": {"paper_data_maintain": "prompt_ready"}}


def finalize(state: MetaInnovationState) -> dict[str, Any]:
    root = _root(state)
    project_dir = _project_dir(state)
    run_dir = _run_dir(state)
    workflow = {
        "graph": "meta_innovation_loop",
        "run_id": state.get("run_id", ""),
        "trigger_reason": state.get("trigger_reason", ""),
        "consensus_ok": state.get("consensus_ok", False),
        "decision": state.get("decision", {}),
        "verdict": "PASS" if state.get("consensus_ok") else "PENDING_REVIEWS",
    }
    (run_dir / "meta_innovation_workflow.json").write_text(
        json.dumps(workflow, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    append_mil_history(
        project_dir,
        {
            "run_id": state.get("run_id", ""),
            "as_of": state.get("as_of", ""),
            "consensus_ok": state.get("consensus_ok", False),
            "top_target": (state.get("decision") or {}).get("target_node", ""),
        },
    )
    mark_trigger_run(project_dir, "meta_innovation", "meta_innovation_loop")
    append_graph_trace(run_dir, {"node": "finalize", "graph": "meta_innovation_loop", "verdict": workflow["verdict"]})
    return {"verdict": workflow["verdict"], "events": {"finalize": workflow}}


def _build_meta_innovation_graph() -> StateGraph:
    g: StateGraph = StateGraph(MetaInnovationState)
    for name, fn in [
        ("setup", setup),
        ("collect_observations", collect_observations),
        ("beci_assess", beci_assess),
        ("skill_to_obsidian", skill_to_obsidian),
        ("subagent_verify", subagent_verify),
        ("multi_llm_review", multi_llm_review),
        ("consensus_decide", consensus_decide),
        ("dispatch_intervention", dispatch_intervention),
        ("paper_data_maintain", paper_data_maintain),
        ("finalize", finalize),
    ]:
        g.add_node(name, fn)

    g.set_entry_point("setup")
    g.add_edge("setup", "collect_observations")
    g.add_edge("collect_observations", "beci_assess")
    g.add_edge("beci_assess", "skill_to_obsidian")
    g.add_edge("skill_to_obsidian", "subagent_verify")
    g.add_edge("subagent_verify", "multi_llm_review")
    g.add_edge("multi_llm_review", "consensus_decide")
    g.add_edge("consensus_decide", "dispatch_intervention")
    g.add_edge("dispatch_intervention", "paper_data_maintain")
    g.add_edge("paper_data_maintain", "finalize")
    g.add_edge("finalize", END)
    return g


def build_meta_innovation_graph():
    return _build_meta_innovation_graph().compile(checkpointer=MemorySaver())


def build_meta_innovation_graph_interruptible(checkpointer: MemorySaver | None = None):
    cp = checkpointer or MemorySaver()
    return _build_meta_innovation_graph().compile(
        checkpointer=cp,
        interrupt_after=list(_MIL_NODES),
    )


def run_meta_innovation_loop(
    root: Path,
    project_id: str,
    *,
    trigger_reason: str = "manual",
    thread_id: str = "default",
) -> dict[str, Any]:
    graph = build_meta_innovation_graph()
    project_dir = root / "projects" / project_id
    initial: MetaInnovationState = {
        "root": str(root.resolve()),
        "project_id": project_id,
        "project_dir": str(project_dir.resolve()),
        "trigger_reason": trigger_reason,
    }
    config = {"configurable": {"thread_id": thread_id}}
    return graph.invoke(initial, config=config)