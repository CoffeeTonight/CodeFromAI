"""Graph session API — LLM reads flow spec, calls tick/resume; graph calls LLM at llm nodes."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Literal

from langgraph.checkpoint.memory import MemorySaver

from soc_verify.config import load_user_config
from soc_verify.graph_llm_bridge import invoke_llm_from_graph
from soc_verify.graph_spec import load_flow_spec, node_spec
from soc_verify.graphs.orchestrator import build_orchestrator_graph_interruptible
from soc_verify.graphs.verify_group import build_verify_group_graph_interruptible
from soc_verify.models import load_yaml, save_yaml
from soc_verify.node_contract import (
    audit_trace_sequence,
    sandbox_payload_for_node,
    validate_exit_contract,
    validate_transition,
)
from soc_verify.tool_sandbox import (
    SandboxResult,
    sandbox_write_file,
    validate_tool_invoke,
    validate_write_path,
)


_CHECKPOINTER = MemorySaver()


@dataclass
class GraphSessionMeta:
    session_id: str
    root: str
    graph_id: Literal["orchestrator", "verify_group"]
    thread_id: str
    mode: str = "single_verify"
    project_id: str = ""
    stage: str = ""
    group: str = ""
    started: bool = False
    finished: bool = False
    last_completed_node: str = ""
    waiting_for: str = ""  # llm | platform | ""
    llm_invoked_nodes: list[str] = field(default_factory=list)
    contract_blocks: list[dict[str, Any]] = field(default_factory=list)


def _sessions_dir(root: Path) -> Path:
    d = root / "runs" / "graph_sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _meta_path(root: Path, session_id: str) -> Path:
    return _sessions_dir(root) / f"{session_id}.yaml"


def save_meta(root: Path, meta: GraphSessionMeta) -> None:
    save_yaml(
        _meta_path(root, meta.session_id),
        {
            "session_id": meta.session_id,
            "root": meta.root,
            "graph_id": meta.graph_id,
            "thread_id": meta.thread_id,
            "mode": meta.mode,
            "project_id": meta.project_id,
            "stage": meta.stage,
            "group": meta.group,
            "started": meta.started,
            "finished": meta.finished,
            "last_completed_node": meta.last_completed_node,
            "waiting_for": meta.waiting_for,
            "llm_invoked_nodes": meta.llm_invoked_nodes,
            "contract_blocks": meta.contract_blocks,
        },
    )


def load_meta(root: Path, session_id: str) -> GraphSessionMeta:
    data = load_yaml(_meta_path(root, session_id))
    return GraphSessionMeta(
        session_id=data["session_id"],
        root=data["root"],
        graph_id=data["graph_id"],
        thread_id=data.get("thread_id", data["session_id"]),
        mode=data.get("mode", ""),
        project_id=data.get("project_id", ""),
        stage=data.get("stage", ""),
        group=data.get("group", ""),
        started=bool(data.get("started")),
        finished=bool(data.get("finished")),
        last_completed_node=data.get("last_completed_node", ""),
        waiting_for=data.get("waiting_for", ""),
        llm_invoked_nodes=list(data.get("llm_invoked_nodes") or []),
        contract_blocks=list(data.get("contract_blocks") or []),
    )


def _verify_run_dir(root: Path, state: dict[str, Any]) -> Path | None:
    pd = state.get("project_dir")
    rid = state.get("run_id")
    if pd and rid:
        return Path(pd) / "runs" / str(rid)
    return None


def _project_dir(state: dict[str, Any]) -> Path | None:
    pd = state.get("project_dir")
    return Path(pd) if pd else None


def _needs_llm_invoke(spec: dict[str, Any], graph_id: str, node_id: str, state: dict[str, Any]) -> bool:
    ns = node_spec(spec, graph_id, node_id)
    if not ns:
        return False
    actor = ns.get("actor", "")
    if actor == "llm_when_runner_llm":
        return state.get("runner") == "llm"
    if actor in ("llm", "llm_assisted", "llm_executor"):
        return True
    return bool(ns.get("llm_trigger")) and state.get("runner") == "llm"


def _record_contract_block(meta: GraphSessionMeta, block: dict[str, Any]) -> None:
    meta.contract_blocks.append(block)
    if len(meta.contract_blocks) > 50:
        meta.contract_blocks = meta.contract_blocks[-50:]


def start_session(
    root: Path,
    *,
    graph_id: Literal["orchestrator", "verify_group"] = "verify_group",
    mode: str = "single_verify",
    project_id: str = "",
    stage: str = "",
    group: str = "",
    orchestrator_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    session_id = uuid.uuid4().hex[:12]
    thread_id = session_id
    meta = GraphSessionMeta(
        session_id=session_id,
        root=str(root),
        graph_id=graph_id,
        thread_id=thread_id,
        mode=mode,
        project_id=project_id,
        stage=stage,
        group=group,
    )
    save_meta(root, meta)

    spec = load_flow_spec(root)
    initial: dict[str, Any]
    if graph_id == "verify_group":
        project_dir = root / "projects" / project_id
        initial = {
            "project_id": project_id,
            "project_dir": str(project_dir.resolve()),
            "stage": stage,
            "group": group,
        }
        if orchestrator_context:
            initial["orchestrator_run_id"] = orchestrator_context.get("orchestrator_run_id", "")
            if orchestrator_context.get("group_context"):
                initial["group_context"] = orchestrator_context["group_context"]
    else:
        initial = {
            "root": str(root),
            "mode": mode,
            "project_id": project_id,
            "stage": stage,
            "group": group,
        }

    (_sessions_dir(root) / f"{session_id}_initial.json").write_text(
        json.dumps(initial, indent=2),
        encoding="utf-8",
    )

    return {
        "session_id": session_id,
        "graph_id": graph_id,
        "flow_spec": str((root / "registry" / "graph_flow_spec.yaml").resolve()),
        "node_contract": str((root / "registry" / "node_contract.yaml").resolve()),
        "flow_spec_inline": spec,
        "entry_node": (spec.get("graphs") or {}).get(graph_id, {}).get("entry"),
        "graph_api": {
            "status": f"soc-verify --root {root} graph status --session {session_id}",
            "tick": f"soc-verify --root {root} graph tick --session {session_id}",
            "resume": f"soc-verify --root {root} graph resume --session {session_id}",
            "invoke_llm": f"soc-verify --root {root} graph invoke-llm --session {session_id}",
            "sandbox": f"soc-verify --root {root} graph sandbox --session {session_id}",
        },
        "initial_state": initial,
    }


def _get_compiled_graph(graph_id: str):
    if graph_id == "verify_group":
        return build_verify_group_graph_interruptible(_CHECKPOINTER)
    return build_orchestrator_graph_interruptible(_CHECKPOINTER)


def session_status(root: Path, session_id: str) -> dict[str, Any]:
    root = root.resolve()
    meta = load_meta(root, session_id)
    spec = load_flow_spec(root)
    config = {"configurable": {"thread_id": meta.thread_id}}
    graph = _get_compiled_graph(meta.graph_id)
    snap = graph.get_state(config)

    next_nodes = list(snap.next) if snap.next else []
    current_node = next_nodes[0] if next_nodes else ("END" if meta.finished else meta.last_completed_node)
    state_values = dict(snap.values) if snap.values else {}

    ns = node_spec(spec, meta.graph_id, current_node) if current_node != "END" else None
    run_dir = _verify_run_dir(root, state_values) if meta.graph_id == "verify_group" else None

    sandbox = None
    exit_contract = None
    if current_node and current_node != "END":
        sandbox = sandbox_payload_for_node(
            root,
            meta.graph_id,
            current_node,
            state=state_values,
            run_dir=run_dir,
        )
        exit_contract = validate_exit_contract(
            root,
            meta.graph_id,
            current_node,
            state=state_values,
            run_dir=run_dir,
        ).to_dict()

    return {
        "session_id": session_id,
        "graph_id": meta.graph_id,
        "flow_spec": str(root / "registry" / "graph_flow_spec.yaml"),
        "node_contract": str(root / "registry" / "node_contract.yaml"),
        "finished": meta.finished or not next_nodes,
        "waiting_for": meta.waiting_for,
        "last_completed_node": meta.last_completed_node,
        "current_node": current_node,
        "next_nodes": next_nodes,
        "current_node_spec": ns,
        "node_sandbox": sandbox,
        "exit_contract": exit_contract,
        "contract_blocks": meta.contract_blocks[-5:],
        "state": state_values,
        "graph_api": {
            "tick": f"soc-verify --root {root} graph tick --session {session_id}",
            "resume": f"soc-verify --root {root} graph resume --session {session_id}",
            "invoke_llm": f"soc-verify --root {root} graph invoke-llm --session {session_id}",
            "sandbox": f"soc-verify --root {root} graph sandbox --session {session_id}",
        },
    }


def _blocked_response(
    root: Path,
    meta: GraphSessionMeta,
    *,
    reason: str,
    contract: dict[str, Any],
    pending: str,
) -> dict[str, Any]:
    _record_contract_block(meta, {"pending": pending, "reason": reason, **contract})
    save_meta(root, meta)
    out = session_status(root, meta.session_id)
    out["tick"] = "blocked"
    out["blocked_reason"] = reason
    out["contract"] = contract
    return out


def session_tick(root: Path, session_id: str, *, auto_invoke_llm: bool = True) -> dict[str, Any]:
    """Advance LangGraph by one step. LLM nodes require exit contract before invoke."""
    root = root.resolve()
    meta = load_meta(root, session_id)
    spec = load_flow_spec(root)
    config = {"configurable": {"thread_id": meta.thread_id}}
    graph = _get_compiled_graph(meta.graph_id)

    initial_path = _sessions_dir(root) / f"{session_id}_initial.json"
    if not meta.started and initial_path.is_file():
        initial = json.loads(initial_path.read_text(encoding="utf-8"))
        graph.invoke(initial, config)
        meta.started = True
        snap = graph.get_state(config)
        next_nodes = list(snap.next) if snap.next else []
        if next_nodes:
            meta.last_completed_node = "setup"
        save_meta(root, meta)
        out = session_status(root, session_id)
        out["tick"] = "ok"
        return out

    snap_before = graph.get_state(config)
    next_nodes = list(snap_before.next) if snap_before.next else []
    if not next_nodes:
        meta.finished = True
        save_meta(root, meta)
        return session_status(root, session_id)

    pending = next_nodes[0]
    state_values = dict(snap_before.values) if snap_before.values else {}
    run_dir = _verify_run_dir(root, state_values) if meta.graph_id == "verify_group" else None

    if meta.last_completed_node:
        edge = validate_transition(root, meta.graph_id, meta.last_completed_node, pending)
        if not edge.ok:
            return _blocked_response(
                root,
                meta,
                reason="illegal_transition",
                contract=edge.to_dict(),
                pending=pending,
            )

    is_llm = _needs_llm_invoke(spec, meta.graph_id, pending, state_values)
    llm_ready = pending in meta.llm_invoked_nodes

    if is_llm and llm_ready:
        exit_result = validate_exit_contract(
            root,
            meta.graph_id,
            pending,
            state=state_values,
            run_dir=run_dir,
        )
        if not exit_result.ok:
            meta.waiting_for = "llm"
            return _blocked_response(
                root,
                meta,
                reason="exit_contract",
                contract=exit_result.to_dict(),
                pending=pending,
            )
        meta.waiting_for = ""

    elif is_llm and auto_invoke_llm and not llm_ready:
        try:
            cfg = load_user_config(root)
        except FileNotFoundError:
            cfg = None
        invoke_llm_from_graph(
            root=root,
            session_id=session_id,
            graph_id=meta.graph_id,
            node_id=pending,
            state_snapshot=state_values,
            run_dir=run_dir,
            config=cfg,
        )
        meta.llm_invoked_nodes.append(pending)
        meta.waiting_for = "llm"
        save_meta(root, meta)

        exit_result = validate_exit_contract(
            root,
            meta.graph_id,
            pending,
            state=state_values,
            run_dir=run_dir,
        )
        if not exit_result.ok:
            out = session_status(root, session_id)
            out["tick"] = "waiting"
            out["message"] = "llm_invoke_sent; write required artifacts then resume"
            out["exit_contract"] = exit_result.to_dict()
            return out

        meta.waiting_for = ""

    graph.invoke(None, config)

    snap = graph.get_state(config)
    next_after = list(snap.next) if snap.next else []
    state_after = dict(snap.values) if snap.values else {}

    trace_audit = audit_trace_sequence(
        run_dir,
        graph_id=meta.graph_id,
        completed_node=pending,
        root=root,
    )
    if not trace_audit.ok:
        _record_contract_block(meta, trace_audit.to_dict())

    platform_exit = validate_exit_contract(
        root,
        meta.graph_id,
        pending,
        state=state_after,
        run_dir=_verify_run_dir(root, state_after) if meta.graph_id == "verify_group" else None,
    )
    if not platform_exit.ok and not is_llm:
        _record_contract_block(meta, platform_exit.to_dict())

    meta.last_completed_node = pending
    meta.waiting_for = ""
    if not next_after:
        meta.finished = True
    else:
        nxt = next_after[0]
        if _needs_llm_invoke(spec, meta.graph_id, nxt, state_after):
            meta.waiting_for = "llm"

    save_meta(root, meta)

    out = session_status(root, session_id)
    out["tick"] = "ok"
    out["completed_node"] = pending
    if not platform_exit.ok and not is_llm:
        out["platform_exit_warning"] = platform_exit.to_dict()
    return out


def session_resume(root: Path, session_id: str) -> dict[str, Any]:
    """Alias for tick — LLM calls after completing current node work."""
    return session_tick(root, session_id, auto_invoke_llm=True)


def session_invoke_llm(root: Path, session_id: str) -> dict[str, Any]:
    """Explicit graph→LLM call at current pending node."""
    root = root.resolve()
    meta = load_meta(root, session_id)
    spec = load_flow_spec(root)
    config = {"configurable": {"thread_id": meta.thread_id}}
    graph = _get_compiled_graph(meta.graph_id)
    snap = graph.get_state(config)
    next_nodes = list(snap.next) if snap.next else []
    if not next_nodes:
        return {"error": "no_pending_node", "status": session_status(root, session_id)}

    pending = next_nodes[0]
    state_values = dict(snap.values) if snap.values else {}
    run_dir = _verify_run_dir(root, state_values) if meta.graph_id == "verify_group" else None
    try:
        cfg = load_user_config(root)
    except FileNotFoundError:
        cfg = None

    result = invoke_llm_from_graph(
        root=root,
        session_id=session_id,
        graph_id=meta.graph_id,
        node_id=pending,
        state_snapshot=state_values,
        run_dir=run_dir,
        config=cfg,
    )
    if pending not in meta.llm_invoked_nodes:
        meta.llm_invoked_nodes.append(pending)
    meta.waiting_for = "llm"
    save_meta(root, meta)

    return {
        "session_id": session_id,
        "node": pending,
        "node_spec": node_spec(spec, meta.graph_id, pending),
        "node_sandbox": sandbox_payload_for_node(
            root,
            meta.graph_id,
            pending,
            state=state_values,
            run_dir=run_dir,
        ),
        "llm": {
            "mode": result.mode,
            "invoked": result.invoked,
            "message": result.message,
        },
        "status": session_status(root, session_id),
    }


def session_sandbox(
    root: Path,
    session_id: str,
    *,
    action: str,
    tool: str = "",
    path: str = "",
    content: str | None = None,
) -> dict[str, Any]:
    """Validate or execute sandboxed tool/write for current graph node only."""
    root = root.resolve()
    meta = load_meta(root, session_id)
    config = {"configurable": {"thread_id": meta.thread_id}}
    graph = _get_compiled_graph(meta.graph_id)
    snap = graph.get_state(config)
    next_nodes = list(snap.next) if snap.next else []
    if not next_nodes:
        return {"ok": False, "error": "no_pending_node"}

    node_id = next_nodes[0]
    state_values = dict(snap.values) if snap.values else {}
    run_dir = _verify_run_dir(root, state_values) if meta.graph_id == "verify_group" else None
    project_dir = _project_dir(state_values)

    if action == "capabilities":
        return {
            "ok": True,
            "session_id": session_id,
            "node": node_id,
            "sandbox": sandbox_payload_for_node(
                root,
                meta.graph_id,
                node_id,
                state=state_values,
                run_dir=run_dir,
            ),
        }

    if action == "tool":
        if not tool:
            return {"ok": False, "error": "missing_tool"}
        result = validate_tool_invoke(
            root,
            session_id=session_id,
            graph_id=meta.graph_id,
            node_id=node_id,
            tool_name=tool,
            state=state_values,
            run_dir=run_dir,
        )
        return {"session_id": session_id, "node": node_id, **result.to_dict()}

    if action in ("validate_write", "write"):
        if not path:
            return {"ok": False, "error": "missing_path"}
        target = Path(path)
        if not target.is_absolute():
            target = (root / path).resolve()
        if action == "validate_write":
            result = validate_write_path(
                root,
                session_id=session_id,
                graph_id=meta.graph_id,
                node_id=node_id,
                target_path=target,
                state=state_values,
                project_dir=project_dir,
            )
            return {"session_id": session_id, "node": node_id, **result.to_dict()}
        if content is None:
            return {"ok": False, "error": "missing_content"}
        result = sandbox_write_file(
            root,
            session_id=session_id,
            graph_id=meta.graph_id,
            node_id=node_id,
            target_path=target,
            content=content,
            state=state_values,
            project_dir=project_dir,
        )
        return {"session_id": session_id, "node": node_id, **result.to_dict()}

    return {"ok": False, "error": f"unknown_action:{action}"}


def run_until_done(root: Path, session_id: str, *, max_ticks: int = 80) -> dict[str, Any]:
    for _ in range(max_ticks):
        st = session_status(root, session_id)
        if st.get("finished"):
            return st
        tick = session_tick(root, session_id)
        if tick.get("tick") in ("blocked", "waiting"):
            tick["finished"] = False
            return tick
    return session_status(root, session_id)