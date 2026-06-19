"""Runtime child-graph evidence enforcement — blocks graph tick when evidence missing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from soc_verify.child_graph import child_graphs_for_graph, load_child_graph_spec
from soc_verify.node_evidence import validate_step_evidence


# Parent node → child_graph_spec key
NODE_CHILD_MAP: dict[str, str] = {
    "run_gate": "run_gate",
    "diagnose_env": "bridge_loop",
    "patch_bridge": "bridge_loop",
    "parity_check": "runner_loop",
    "run_codegen": "runner_loop",
    "promote": "promote",
    "meta_propose": "meta_propose",
}


@dataclass
class ChildRuntimeResult:
    ok: bool
    node_id: str
    child_key: str
    failed_steps: list[str]
    issues: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "node_id": self.node_id,
            "child_key": self.child_key,
            "failed_steps": self.failed_steps,
            "issues": self.issues,
            "contract": "child_runtime_v1",
        }


def child_key_for_node(node_id: str) -> str | None:
    return NODE_CHILD_MAP.get(node_id)


def validate_child_runtime(
    root: Path,
    graph_id: str,
    node_id: str,
    *,
    state: dict[str, Any],
    run_dir: Path | None,
) -> ChildRuntimeResult:
    """All child steps for this parent node must pass evidence before tick advance."""
    child_key = child_key_for_node(node_id)
    if not child_key or run_dir is None:
        return ChildRuntimeResult(ok=True, node_id=node_id, child_key="", failed_steps=[], issues=[])

    spec = load_child_graph_spec(root)
    block = child_graphs_for_graph(spec, graph_id).get(child_key) or {}
    steps = block.get("steps") or []

    failed: list[str] = []
    issues: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        parent_node = step.get("parent_node")
        if parent_node and parent_node != node_id:
            continue
        ev = validate_step_evidence(step, root=root, graph_id=graph_id, state=state, run_dir=run_dir)
        if not ev.ok:
            failed.append(ev.step_id)
            issues.extend(ev.issues)

    return ChildRuntimeResult(
        ok=not failed,
        node_id=node_id,
        child_key=child_key,
        failed_steps=failed,
        issues=issues,
    )


def validate_child_before_enter(
    root: Path,
    graph_id: str,
    node_id: str,
    *,
    state: dict[str, Any],
    run_dir: Path | None,
) -> ChildRuntimeResult:
    """Before entering node: prior sibling steps in same child graph should be satisfied."""
    return validate_child_runtime(root, graph_id, node_id, state=state, run_dir=run_dir)


def validate_child_after_complete(
    root: Path,
    graph_id: str,
    completed_node: str,
    *,
    state: dict[str, Any],
    run_dir: Path | None,
) -> ChildRuntimeResult:
    """After node completes: all steps for this parent must have evidence."""
    return validate_child_runtime(root, graph_id, completed_node, state=state, run_dir=run_dir)