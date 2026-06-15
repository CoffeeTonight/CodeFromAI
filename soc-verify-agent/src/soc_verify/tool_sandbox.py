"""Node-scoped tool and write-path sandbox — LLM cannot act outside current graph node."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from soc_verify.node_contract import (
    path_allowed_for_node,
    sandbox_payload_for_node,
)


@dataclass
class SandboxResult:
    ok: bool
    action: str
    reason: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "action": self.action,
            "reason": self.reason,
            "details": self.details,
        }


def _audit_path(root: Path, session_id: str) -> Path:
    d = root / "runs" / "graph_sessions" / session_id
    d.mkdir(parents=True, exist_ok=True)
    return d / "sandbox_audit.jsonl"


def _append_audit(root: Path, session_id: str, entry: dict[str, Any]) -> None:
    path = _audit_path(root, session_id)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def validate_tool_invoke(
    root: Path,
    *,
    session_id: str,
    graph_id: str,
    node_id: str,
    tool_name: str,
    state: dict[str, Any],
    run_dir: Path | None = None,
) -> SandboxResult:
    payload = sandbox_payload_for_node(root, graph_id, node_id, state=state, run_dir=run_dir)
    allowed = set(payload.get("allowed_tools") or [])
    forbidden = set(payload.get("forbidden_actions") or [])

    if tool_name in forbidden:
        result = SandboxResult(ok=False, action="tool", reason="forbidden_action", details={"tool": tool_name})
    elif tool_name not in allowed:
        result = SandboxResult(
            ok=False,
            action="tool",
            reason="tool_not_allowed_for_node",
            details={"tool": tool_name, "allowed_tools": sorted(allowed)},
        )
    else:
        result = SandboxResult(ok=True, action="tool", reason="allowed", details={"tool": tool_name})

    _append_audit(
        root,
        session_id,
        {
            "kind": "tool",
            "session_id": session_id,
            "graph": graph_id,
            "node": node_id,
            "tool": tool_name,
            "ok": result.ok,
            "reason": result.reason,
        },
    )
    return result


def validate_write_path(
    root: Path,
    *,
    session_id: str,
    graph_id: str,
    node_id: str,
    target_path: Path,
    state: dict[str, Any],
    project_dir: Path | None = None,
) -> SandboxResult:
    ok, reason = path_allowed_for_node(
        root,
        graph_id,
        node_id,
        target_path,
        project_dir=project_dir,
    )
    result = SandboxResult(
        ok=ok,
        action="write",
        reason=reason,
        details={"path": str(target_path.resolve())},
    )
    _append_audit(
        root,
        session_id,
        {
            "kind": "write",
            "session_id": session_id,
            "graph": graph_id,
            "node": node_id,
            "path": str(target_path.resolve()),
            "ok": ok,
            "reason": reason,
        },
    )
    return result


def sandbox_write_file(
    root: Path,
    *,
    session_id: str,
    graph_id: str,
    node_id: str,
    target_path: Path,
    content: str,
    state: dict[str, Any],
    project_dir: Path | None = None,
) -> SandboxResult:
    gate = validate_write_path(
        root,
        session_id=session_id,
        graph_id=graph_id,
        node_id=node_id,
        target_path=target_path,
        state=state,
        project_dir=project_dir,
    )
    if not gate.ok:
        return gate

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(content, encoding="utf-8")
    gate.details["bytes_written"] = len(content.encode("utf-8"))
    gate.reason = "written"
    return gate