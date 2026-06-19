"""Node gate — mandatory evidence before LangGraph transitions."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from soc_verify.config import UserConfig, load_user_config
from soc_verify.graph_spec import load_flow_spec, node_spec
from soc_verify.models import load_yaml, save_yaml
from soc_verify.node_contract import (
    build_contract_context,
    load_node_contract,
    node_contract_block,
    _eval_check_any_of,
)
from soc_verify.node_evidence import _eval_custom_check


SPEC_NAME = "node_gate_spec.yaml"
DECL_CONTRACT = "node_gate_decl_v1"
PASS_CONTRACT = "node_gate_pass_v1"


class NodeGateBlocked(Exception):
    def __init__(self, result: NodeGateResult) -> None:
        self.result = result
        super().__init__("; ".join(result.issues))


@dataclass
class NodeGateResult:
    ok: bool
    node: str
    graph_id: str
    phase: str
    purpose_ko: str = ""
    issues: list[str] = field(default_factory=list)
    checks: list[dict[str, Any]] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    contract: str = "node_gate_v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "node": self.node,
            "graph_id": self.graph_id,
            "phase": self.phase,
            "purpose_ko": self.purpose_ko,
            "issues": self.issues,
            "checks": self.checks,
            "sources": self.sources,
            "contract": self.contract,
        }


def spec_path(root: Path | None = None) -> Path:
    root = root or Path.cwd()
    p = root / "registry" / SPEC_NAME
    if not p.is_file():
        p = Path(__file__).resolve().parents[2] / "registry" / SPEC_NAME
    return p


def load_node_gate_spec(root: Path | None = None) -> dict[str, Any]:
    return load_yaml(spec_path(root)) or {}


def gate_dir(run_dir: Path) -> Path:
    return run_dir / "node_gate"


def pass_artifact_path(run_dir: Path, node_id: str) -> Path:
    return gate_dir(run_dir) / f"{node_id}_pass.json"


def decl_artifact_path(run_dir: Path, node_id: str) -> Path:
    return gate_dir(run_dir) / f"{node_id}_decl.json"


def user_gates_path(project_dir: Path | None) -> Path | None:
    if not project_dir:
        return None
    return project_dir / "meta" / "node_gates.yaml"


def _node_block(spec: dict[str, Any], graph_id: str, node_id: str) -> dict[str, Any]:
    graphs = spec.get("graphs") or {}
    g = graphs.get(graph_id) or {}
    nodes = g.get("nodes") or {}
    return nodes.get(node_id) or {}


def _purpose_ko(
    spec: dict[str, Any],
    graph_id: str,
    node_id: str,
    *,
    root: Path,
) -> str:
    block = _node_block(spec, graph_id, node_id)
    if block.get("purpose_ko"):
        return str(block["purpose_ko"])
    flow = node_spec(load_flow_spec(root), graph_id, node_id) or {}
    action = str(flow.get("action") or "").strip()
    if action:
        return action[:240]
    return f"{graph_id}/{node_id}"


def _platform_checks(
    root: Path,
    graph_id: str,
    node_id: str,
    *,
    gate_spec: dict[str, Any],
    include_contract_exit: bool = True,
) -> list[dict[str, Any]]:
    block = _node_block(gate_spec, graph_id, node_id)
    checks: list[dict[str, Any]] = list(block.get("platform_checks") or [])
    if include_contract_exit and block.get("use_node_contract_exit"):
        nc = node_contract_block(load_node_contract(root), graph_id, node_id) or {}
        checks.extend(list(nc.get("requires_exit") or []))
    if not checks and not block.get("use_node_contract_exit"):
        checks.append({"type": "trace_contains", "node": node_id})
    return checks


def _user_checks(
    project_dir: Path | None,
    graph_id: str,
    node_id: str,
    *,
    config: UserConfig | None = None,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if project_dir:
        path = user_gates_path(project_dir)
        if path and path.is_file():
            data = load_yaml(path) or {}
            node_cfg = ((data.get(graph_id) or {}).get(node_id)) or {}
            checks.extend(list(node_cfg.get("extra_checks") or node_cfg.get("checks") or []))
    if config:
        overrides = (config.raw.get("node_gates") or {}).get(graph_id) or {}
        node_cfg = overrides.get(node_id) or {}
        checks.extend(list(node_cfg.get("extra_checks") or node_cfg.get("checks") or []))
    return checks


def load_llm_gate_decl(run_dir: Path | None, node_id: str) -> dict[str, Any] | None:
    if run_dir is None:
        return None
    path = decl_artifact_path(run_dir, node_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict) and data.get("contract") == DECL_CONTRACT and data.get("node") == node_id:
        return data
    return None


def _llm_checks(
    gate_spec: dict[str, Any],
    graph_id: str,
    node_id: str,
    run_dir: Path | None,
) -> tuple[list[dict[str, Any]], str]:
    block = _node_block(gate_spec, graph_id, node_id)
    if not block.get("llm_may_extend", True):
        return [], ""
    decl = load_llm_gate_decl(run_dir, node_id)
    if not decl:
        return [], ""
    checks = [c for c in (decl.get("checks") or []) if isinstance(c, dict)]
    summary = str(decl.get("summary_ko") or decl.get("purpose_ko") or "")
    return checks, summary


def merge_gate_checks(
    root: Path,
    graph_id: str,
    node_id: str,
    *,
    state: dict[str, Any],
    run_dir: Path | None,
    config: UserConfig | None = None,
    include_contract_exit: bool = True,
) -> tuple[list[dict[str, Any]], str, list[str]]:
    gate_spec = load_node_gate_spec(root)
    project_dir = Path(state["project_dir"]) if state.get("project_dir") else None
    purpose = _purpose_ko(gate_spec, graph_id, node_id, root=root)

    platform = _platform_checks(
        root, graph_id, node_id, gate_spec=gate_spec, include_contract_exit=include_contract_exit
    )
    user = _user_checks(project_dir, graph_id, node_id, config=config)
    llm, llm_summary = _llm_checks(gate_spec, graph_id, node_id, run_dir)

    sources: list[str] = []
    if platform:
        sources.append("platform")
    if user:
        sources.append("user")
    if llm:
        sources.append("llm")

    return platform + user + llm, purpose, sources


def _eval_gate_checks(
    checks: list[dict[str, Any]],
    *,
    root: Path,
    graph_id: str,
    state: dict[str, Any],
    run_dir: Path | None,
) -> list[str]:
    if not run_dir or not run_dir.is_dir():
        run_dir_path = Path(state.get("project_dir", ".")) / "runs" / str(state.get("run_id", "none"))
        run_dir = run_dir_path if run_dir_path.is_dir() else (Path.cwd() / "runs" / "none")

    ctx = build_contract_context(root=root, graph_id=graph_id, state=state, run_dir=run_dir)
    issues: list[str] = []
    for check in checks:
        if not isinstance(check, dict):
            continue
        ctype = check.get("type", "")
        if ctype in ("state_field_set", "state_field_equals", "trace_contains", "error_kind_in", "events_bumped"):
            issues.extend(
                _eval_custom_check(
                    check,
                    ctx=ctx,
                    state=state,
                    run_dir=run_dir,
                    root=root,
                )
            )
        else:
            issues.extend(_eval_check_any_of(check, ctx))
    return issues


def load_gate_pass(run_dir: Path | None, node_id: str) -> dict[str, Any] | None:
    if run_dir is None:
        return None
    path = pass_artifact_path(run_dir, node_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict) and data.get("contract") == PASS_CONTRACT:
        return data
    return None


def validate_node_gate(
    root: Path,
    graph_id: str,
    node_id: str,
    *,
    state: dict[str, Any],
    run_dir: Path | None,
    phase: str = "exit",
    config: UserConfig | None = None,
) -> NodeGateResult:
    """All merged checks must pass; valid pass artifact with summary also satisfies exit."""
    gate_spec = load_node_gate_spec(root)
    purpose = _purpose_ko(gate_spec, graph_id, node_id, root=root)
    include_contract_exit = phase == "exit"
    checks, _, sources = merge_gate_checks(
        root,
        graph_id,
        node_id,
        state=state,
        run_dir=run_dir,
        config=config,
        include_contract_exit=include_contract_exit,
    )

    rules = gate_spec.get("default_rules") or {}
    min_summary = int(rules.get("min_summary_chars", 8))

    existing = load_gate_pass(run_dir, node_id)
    if existing and existing.get("node") == node_id and existing.get("checks_ok"):
        summary = str(existing.get("summary_ko") or "")
        if len(summary.strip()) >= min_summary:
            return NodeGateResult(
                ok=True,
                node=node_id,
                graph_id=graph_id,
                phase=phase,
                purpose_ko=purpose,
                checks=checks,
                sources=sources + ["pass_artifact"],
            )

    issues = _eval_gate_checks(
        checks, root=root, graph_id=graph_id, state=state, run_dir=run_dir
    )
    if issues:
        return NodeGateResult(
            ok=False,
            node=node_id,
            graph_id=graph_id,
            phase=phase,
            purpose_ko=purpose,
            issues=issues,
            checks=checks,
            sources=sources,
        )

    _, llm_summary = _llm_checks(gate_spec, graph_id, node_id, run_dir)
    summary = llm_summary.strip()
    if len(summary) < min_summary:
        summary = f"{purpose} — gate checks {len(checks)} passed"

    return NodeGateResult(
        ok=True,
        node=node_id,
        graph_id=graph_id,
        phase=phase,
        purpose_ko=purpose,
        checks=checks,
        sources=sources,
    )


def write_node_gate_pass(
    run_dir: Path,
    graph_id: str,
    node_id: str,
    result: NodeGateResult,
    *,
    root: Path | None = None,
    summary_ko: str | None = None,
    evidence: list[dict[str, Any]] | None = None,
    outcome: Any | None = None,
) -> Path:
    gate_dir(run_dir).mkdir(parents=True, exist_ok=True)
    rules = load_node_gate_spec(root)
    min_summary = int((rules.get("default_rules") or {}).get("min_summary_chars", 8))
    summary = (summary_ko or result.purpose_ko or "").strip()
    if len(summary) < min_summary:
        summary = f"{result.purpose_ko} — checks passed"

    payload: dict[str, Any] = {
        "contract": PASS_CONTRACT,
        "graph": graph_id,
        "node": node_id,
        "purpose_ko": result.purpose_ko,
        "summary_ko": summary,
        "checks_ok": True,
        "sources": result.sources,
        "check_count": len(result.checks),
        "evidence": evidence or [],
        "passed_at": datetime.now(timezone.utc).isoformat(),
    }
    if outcome is not None:
        payload["outcome"] = outcome.to_dict()
        if outcome.strategy:
            payload["strategy"] = outcome.strategy
    path = pass_artifact_path(run_dir, node_id)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_llm_gate_decl(
    run_dir: Path,
    *,
    node_id: str,
    purpose_ko: str,
    checks: list[dict[str, Any]],
    summary_ko: str = "",
) -> Path:
    gate_dir(run_dir).mkdir(parents=True, exist_ok=True)
    payload = {
        "contract": DECL_CONTRACT,
        "node": node_id,
        "purpose_ko": purpose_ko,
        "summary_ko": summary_ko,
        "checks": checks,
    }
    path = decl_artifact_path(run_dir, node_id)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def save_user_node_gate(
    project_dir: Path,
    graph_id: str,
    node_id: str,
    *,
    extra_checks: list[dict[str, Any]] | None = None,
    purpose_ko: str = "",
) -> Path:
    path = user_gates_path(project_dir)
    assert path is not None
    path.parent.mkdir(parents=True, exist_ok=True)
    data = load_yaml(path) if path.is_file() else {}
    if not isinstance(data, dict):
        data = {}
    g = data.setdefault(graph_id, {})
    block = g.setdefault(node_id, {})
    if extra_checks:
        block["extra_checks"] = extra_checks
    if purpose_ko:
        block["purpose_ko"] = purpose_ko
    save_yaml(path, data)
    return path


def node_gate_payload(
    root: Path,
    graph_id: str,
    node_id: str,
    *,
    state: dict[str, Any],
    run_dir: Path | None,
    config: UserConfig | None = None,
) -> dict[str, Any]:
    gate_spec = load_node_gate_spec(root)
    block = _node_block(gate_spec, graph_id, node_id)
    checks, purpose, sources = merge_gate_checks(
        root, graph_id, node_id, state=state, run_dir=run_dir, config=config
    )
    decl = load_llm_gate_decl(run_dir, node_id)
    passed = load_gate_pass(run_dir, node_id)
    validation = validate_node_gate(
        root, graph_id, node_id, state=state, run_dir=run_dir, config=config
    )
    return {
        "contract": "node_gate_payload_v1",
        "node": node_id,
        "graph": graph_id,
        "purpose_ko": purpose,
        "llm_may_extend": bool(block.get("llm_may_extend", True)),
        "merged_checks": checks,
        "sources": sources,
        "decl_artifact": str(decl_artifact_path(run_dir, node_id)) if run_dir else "",
        "pass_artifact": str(pass_artifact_path(run_dir, node_id)) if run_dir else "",
        "decl": decl,
        "pass": passed,
        "ok": validation.ok,
        "issues": validation.issues,
        "evidence_kinds": gate_spec.get("evidence_kinds") or {},
        "instruction_ko": (gate_spec.get("instruction_ko") or "").strip(),
    }


def enrich_sandbox_payload(payload: dict[str, Any]) -> dict[str, Any]:
    globs = list(payload.get("allowed_write_globs") or [])
    for pattern in (
        "projects/*/runs/*/node_gate/**",
        "projects/*/meta/node_gates.yaml",
    ):
        if pattern not in globs:
            globs.append(pattern)
    tools = list(payload.get("allowed_tools") or [])
    for tool in ("write_node_gate_decl", "write_node_gate_pass"):
        if tool not in tools:
            tools.append(tool)
    payload["allowed_write_globs"] = globs
    payload["allowed_tools"] = tools
    payload["node_gate"] = True
    from soc_verify.node_triage import enrich_sandbox_payload as enrich_triage_sandbox

    return enrich_triage_sandbox(payload)


def finalize_node_gate(
    root: Path,
    graph_id: str,
    node_id: str,
    *,
    state: dict[str, Any],
    run_dir: Path | None,
    summary_ko: str | None = None,
    evidence: list[dict[str, Any]] | None = None,
    config: UserConfig | None = None,
) -> NodeGateResult:
    """Validate merged gate; on success write pass artifact."""
    if config is None:
        try:
            config = load_user_config(root)
        except FileNotFoundError:
            config = None
    result = validate_node_gate(
        root, graph_id, node_id, state=state, run_dir=run_dir, config=config
    )
    if result.ok and run_dir is not None:
        from soc_verify.node_triage import record_outcome_and_strategy

        outcome = record_outcome_and_strategy(
            root,
            graph_id,
            node_id,
            state=state,
            run_dir=run_dir,
            config=config,
        )
        write_node_gate_pass(
            run_dir,
            graph_id,
            node_id,
            result,
            root=root,
            summary_ko=summary_ko,
            evidence=evidence,
            outcome=outcome,
        )
    return result