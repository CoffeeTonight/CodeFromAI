"""Compiled child LangGraphs — evidence-gated sub-flows for multi-step parent nodes.

Parent nodes in verify_group.py remain SSOT for routing; these subgraphs are
reference implementations aligned with registry/child_graph_spec.yaml.
Meta-graph / LANGGRAPH-SUMMARY links here for LLM improvement proposals.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from langgraph.graph import END, StateGraph


class PromoteChildState(TypedDict, total=False):
    run_dir: str
    trust_ok: bool
    promote_decision_ok: bool
    crystallize_ok: bool
    error: str


def promote_trust_step(state: PromoteChildState) -> dict[str, Any]:
    return {"trust_ok": True}


def promote_decision_step(state: PromoteChildState) -> dict[str, Any]:
    if not state.get("trust_ok"):
        return {"error": "trust_evidence_missing", "promote_decision_ok": False}
    return {"promote_decision_ok": True}


def promote_crystallize_step(state: PromoteChildState) -> dict[str, Any]:
    if not state.get("promote_decision_ok"):
        return {"error": "promote_decision_missing", "crystallize_ok": False}
    return {"crystallize_ok": True}


def route_promote_child(state: PromoteChildState) -> Literal["promote_decision", "end"]:
    if state.get("trust_ok"):
        return "promote_decision"
    return "end"


def route_promote_crystallize(state: PromoteChildState) -> Literal["crystallize", "end"]:
    if state.get("promote_decision_ok"):
        return "crystallize"
    return "end"


def build_promote_child_graph():
    """Child graph: trust_evaluate → promote_decision → crystallize_registry."""
    g = StateGraph(PromoteChildState)
    g.add_node("trust_evaluate", promote_trust_step)
    g.add_node("promote_decision", promote_decision_step)
    g.add_node("crystallize", promote_crystallize_step)
    g.set_entry_point("trust_evaluate")
    g.add_conditional_edges("trust_evaluate", route_promote_child, {"promote_decision": "promote_decision", "end": END})
    g.add_conditional_edges(
        "promote_decision",
        route_promote_crystallize,
        {"crystallize": "crystallize", "end": END},
    )
    g.add_edge("crystallize", END)
    return g.compile()


class RunnerLoopChildState(TypedDict, total=False):
    parity_ok: bool
    codegen_round: int
    max_rounds: int


def runner_snapshot_step(state: RunnerLoopChildState) -> dict[str, Any]:
    return {"parity_ok": state.get("parity_ok", False)}


def runner_codegen_step(state: RunnerLoopChildState) -> dict[str, Any]:
    n = int(state.get("codegen_round", 0)) + 1
    return {"codegen_round": n}


def route_runner_loop(state: RunnerLoopChildState) -> Literal["codegen", "end"]:
    if state.get("parity_ok"):
        return "end"
    if int(state.get("codegen_round", 0)) >= int(state.get("max_rounds", 10)):
        return "end"
    return "codegen"


def build_runner_loop_child_graph():
    """Child graph: snapshot_reference ↔ codegen_ops until parity_ok."""
    g = StateGraph(RunnerLoopChildState)
    g.add_node("parity_snapshot", runner_snapshot_step)
    g.add_node("codegen", runner_codegen_step)
    g.set_entry_point("parity_snapshot")
    g.add_conditional_edges(
        "parity_snapshot",
        route_runner_loop,
        {"codegen": "codegen", "end": END},
    )
    g.add_edge("codegen", "parity_snapshot")
    return g.compile()