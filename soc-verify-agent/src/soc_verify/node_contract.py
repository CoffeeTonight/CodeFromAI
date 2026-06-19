"""Node contract — artifact gates and transition audit for LangGraph sessions."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from soc_verify.graph_spec import load_flow_spec, next_nodes_from_spec
from soc_verify.models import load_yaml


@dataclass
class ContractCheckResult:
    ok: bool
    node: str
    phase: str
    issues: list[str] = field(default_factory=list)
    contract: str = "node_contract_v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "node": self.node,
            "phase": self.phase,
            "issues": self.issues,
            "contract": self.contract,
        }


class NodeContractBlocked(Exception):
    def __init__(self, result: ContractCheckResult) -> None:
        self.result = result
        super().__init__("; ".join(result.issues))


def contract_path(root: Path | None = None) -> Path:
    root = root or Path.cwd()
    p = root / "registry" / "node_contract.yaml"
    if not p.is_file():
        p = Path(__file__).resolve().parents[2] / "registry" / "node_contract.yaml"
    return p


def load_node_contract(root: Path | None = None) -> dict[str, Any]:
    return load_yaml(contract_path(root))


def node_contract_block(
    contract: dict[str, Any],
    graph_id: str,
    node_id: str,
) -> dict[str, Any] | None:
    graphs = contract.get("graphs") or {}
    g = graphs.get(graph_id) or {}
    nodes = g.get("nodes") or {}
    block = nodes.get(node_id)
    if not block:
        return None
    return {
        "graph": graph_id,
        "node": node_id,
        "forbidden_global": list(g.get("forbidden_global") or []),
        **block,
    }


def build_contract_context(
    *,
    root: Path,
    graph_id: str,
    state: dict[str, Any],
    run_dir: Path | None = None,
) -> dict[str, Any]:
    project_dir = Path(state["project_dir"]) if state.get("project_dir") else None
    stage = str(state.get("stage", ""))
    group = str(state.get("group", ""))
    project_id = str(state.get("project_id", ""))
    ops_path = ""
    bridge_path = ""
    if project_dir and stage and group:
        ops_path = str(project_dir / "ops" / stage / f"{group}.py")
        bridge_path = str(project_dir / "bridge" / stage / f"{group}.py")

    orch_run_dir = ""
    if graph_id == "orchestrator":
        rid = state.get("run_id", "")
        if rid:
            orch_run_dir = str(root / "runs" / "orchestrator" / str(rid))

    setup_run_dir = ""
    mil_run_dir = ""
    if graph_id == "setup_group" and project_dir:
        rid = state.get("run_id", "")
        if rid:
            setup_run_dir = str(project_dir / "runs" / "setup" / str(rid))
        elif run_dir:
            setup_run_dir = str(run_dir.resolve())
    if graph_id == "meta_innovation_loop" and project_dir:
        rid = state.get("run_id", "")
        if rid:
            mil_run_dir = str(project_dir / "runs" / "meta_innovation" / str(rid))
        elif run_dir:
            mil_run_dir = str(run_dir.resolve())

    return {
        "root": str(root.resolve()),
        "project_id": project_id,
        "project_dir": str(project_dir.resolve()) if project_dir else "",
        "stage": stage,
        "group": group,
        "run_dir": str(run_dir.resolve()) if run_dir else "",
        "ops_path": ops_path,
        "bridge_path": bridge_path,
        "orch_run_dir": orch_run_dir,
        "setup_run_dir": setup_run_dir,
        "mil_run_dir": mil_run_dir,
        "runner": state.get("runner", ""),
        "runner_mode": state.get("runner_mode", ""),
    }


def _resolve_path(template: str, ctx: dict[str, Any]) -> Path:
    text = template.format(**ctx)
    p = Path(text)
    if p.is_absolute():
        return p
    return Path(ctx["root"]) / text


def _eval_check(check: dict[str, Any], ctx: dict[str, Any]) -> list[str]:
    ctype = check.get("type", "")
    if ctype == "file_exists":
        path = _resolve_path(str(check["path"]), ctx)
        if not path.is_file():
            return [f"missing file: {path}"]
        return []
    if ctype == "json_field_true":
        path = _resolve_path(str(check["path"]), ctx)
        field_name = str(check.get("field", "ok"))
        if not path.is_file():
            return [f"missing json: {path}"]
        data = json.loads(path.read_text(encoding="utf-8"))
        if not data.get(field_name):
            return [f"{path.name}.{field_name} is not true"]
        return []
    if ctype == "json_field_equals":
        path = _resolve_path(str(check["path"]), ctx)
        field_name = str(check.get("field", ""))
        expected = check.get("value")
        if not path.is_file():
            return [f"missing json: {path}"]
        data = json.loads(path.read_text(encoding="utf-8"))
        actual = data.get(field_name)
        if actual != expected:
            return [f"{path.name}.{field_name}: expected {expected!r}, got {actual!r}"]
        return []
    return [f"unknown check type: {ctype}"]


def _eval_check_any_of(check: dict[str, Any], ctx: dict[str, Any]) -> list[str]:
    ctype = check.get("type", "")
    if ctype == "any_of":
        subs = check.get("checks") or []
        for sub in subs:
            if not _eval_check(sub, ctx):
                return []
        return [f"any_of: no branch satisfied ({len(subs)} checks)"]
    return _eval_check(check, ctx)


def validate_exit_contract(
    root: Path,
    graph_id: str,
    node_id: str,
    *,
    state: dict[str, Any],
    run_dir: Path | None = None,
) -> ContractCheckResult:
    contract = load_node_contract(root)
    block = node_contract_block(contract, graph_id, node_id)
    if not block:
        return ContractCheckResult(ok=True, node=node_id, phase="exit")

    ctx = build_contract_context(root=root, graph_id=graph_id, state=state, run_dir=run_dir)
    issues: list[str] = []
    for check in block.get("requires_exit") or []:
        issues.extend(_eval_check_any_of(check, ctx))

    return ContractCheckResult(ok=not issues, node=node_id, phase="exit", issues=issues)


def validate_transition(
    root: Path,
    graph_id: str,
    from_node: str,
    to_node: str,
) -> ContractCheckResult:
    if not from_node or from_node == to_node:
        return ContractCheckResult(ok=True, node=to_node, phase="transition")
    spec = load_flow_spec(root)
    allowed = next_nodes_from_spec(spec, graph_id, from_node)
    if to_node in allowed or to_node == "END":
        return ContractCheckResult(ok=True, node=to_node, phase="transition")
    return ContractCheckResult(
        ok=False,
        node=to_node,
        phase="transition",
        issues=[f"illegal edge {from_node} -> {to_node}; allowed: {allowed}"],
    )


def audit_trace_sequence(
    run_dir: Path | None,
    *,
    graph_id: str,
    completed_node: str,
    root: Path,
    from_node: str = "",
) -> ContractCheckResult:
    """Validate edge into completed_node. Prefer explicit from_node (session meta)."""
    if from_node:
        return validate_transition(root, graph_id, from_node, completed_node)

    if run_dir is None or not run_dir.is_dir():
        return ContractCheckResult(ok=True, node=completed_node, phase="trace")

    trace_path = run_dir / "graph_trace.jsonl"
    if not trace_path.is_file():
        return ContractCheckResult(ok=True, node=completed_node, phase="trace")

    lines = [ln for ln in trace_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        return ContractCheckResult(ok=True, node=completed_node, phase="trace")

    last = json.loads(lines[-1])
    prev_node = str(last.get("node", ""))
    if not prev_node:
        return ContractCheckResult(ok=True, node=completed_node, phase="trace")

    return validate_transition(root, graph_id, prev_node, completed_node)


def path_allowed_for_node(
    root: Path,
    graph_id: str,
    node_id: str,
    path: Path,
    *,
    project_dir: Path | None = None,
) -> tuple[bool, str]:
    contract = load_node_contract(root)
    block = node_contract_block(contract, graph_id, node_id)
    if not block:
        return False, "no_node_contract"

    globs = list(block.get("allowed_write_globs") or [])
    if not globs:
        return False, "no_write_globs"

    root = root.resolve()
    path = path.resolve()
    try:
        if project_dir:
            rel = path.relative_to(root)
            rel_str = str(rel).replace("\\", "/")
        else:
            rel_str = str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return False, "path_outside_workspace"

    for pattern in globs:
        if fnmatch(rel_str, pattern):
            return True, "allowed"

    return False, f"path_not_in_allowed_write_globs: {rel_str}"


def sandbox_payload_for_node(
    root: Path,
    graph_id: str,
    node_id: str,
    *,
    state: dict[str, Any],
    run_dir: Path | None = None,
) -> dict[str, Any]:
    contract = load_node_contract(root)
    block = node_contract_block(contract, graph_id, node_id) or {}
    spec = load_flow_spec(root)
    return {
        "contract": "node_sandbox_v1",
        "node": node_id,
        "graph": graph_id,
        "allowed_tools": list(block.get("allowed_tools") or []),
        "allowed_write_globs": list(block.get("allowed_write_globs") or []),
        "forbidden_actions": list(block.get("forbidden_actions") or [])
        + list((contract.get("graphs") or {}).get(graph_id, {}).get("forbidden_global") or []),
        "allowed_next": next_nodes_from_spec(spec, graph_id, node_id),
        "requires_exit": block.get("requires_exit") or [],
        "runner": state.get("runner"),
        "runner_mode": state.get("runner_mode"),
        "run_dir": str(run_dir) if run_dir else "",
        "node_gate_file": str((root / "registry" / "node_gate_spec.yaml").resolve()),
    }