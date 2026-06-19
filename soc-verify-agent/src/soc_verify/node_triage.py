"""Node triage — outcome fail definition and post-fail routing strategies."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from soc_verify.config import UserConfig
from soc_verify.graph_spec import load_flow_spec, next_nodes_from_spec
from soc_verify.models import load_yaml, save_yaml
from soc_verify.node_evidence import _eval_custom_check, _eval_evidence_group
from soc_verify.node_gate import load_node_gate_spec, _node_block as _gate_node_block


SPEC_NAME = "node_triage_spec.yaml"
PLAN_CONTRACT = "node_triage_plan_v1"


@dataclass
class OutcomeResult:
    outcome: Literal["pass", "fail", "unknown"]
    fail_class: str = ""
    rationale_ko: str = ""
    strategy: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "fail_class": self.fail_class,
            "rationale_ko": self.rationale_ko,
            "strategy": self.strategy,
            "contract": "node_outcome_v1",
        }


def triage_spec_path(root: Path | None = None) -> Path:
    root = root or Path.cwd()
    p = root / "registry" / SPEC_NAME
    if not p.is_file():
        p = Path(__file__).resolve().parents[2] / "registry" / SPEC_NAME
    return p


def load_triage_spec(root: Path | None = None) -> dict[str, Any]:
    return load_yaml(triage_spec_path(root)) or {}


def _triage_node_block(spec: dict[str, Any], graph_id: str, node_id: str) -> dict[str, Any]:
    graphs = spec.get("graphs") or {}
    g = graphs.get(graph_id) or {}
    nodes = g.get("nodes") or {}
    return nodes.get(node_id) or {}


def user_triage_path(project_dir: Path | None) -> Path | None:
    if not project_dir:
        return None
    return project_dir / "meta" / "node_triage.yaml"


def triage_plan_path(run_dir: Path, node_id: str) -> Path:
    return run_dir / "node_triage" / f"{node_id}_plan.json"


def load_llm_triage_plan(run_dir: Path | None, node_id: str) -> dict[str, Any] | None:
    if run_dir is None:
        return None
    path = triage_plan_path(run_dir, node_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict) and data.get("contract") == PLAN_CONTRACT and data.get("node") == node_id:
        return data
    return None


def write_triage_plan(
    run_dir: Path,
    *,
    node_id: str,
    fail_class: str,
    route: str,
    rationale_ko: str,
    source: str,
    sequence_action: str = "",
    extra: dict[str, Any] | None = None,
) -> Path:
    d = run_dir / "node_triage"
    d.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "contract": PLAN_CONTRACT,
        "node": node_id,
        "fail_class": fail_class,
        "route": route,
        "rationale_ko": rationale_ko,
        "source": source,
    }
    if sequence_action:
        payload["sequence_action"] = sequence_action
    if extra:
        payload.update(extra)
    path = triage_plan_path(run_dir, node_id)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def save_user_triage_override(
    project_dir: Path,
    graph_id: str,
    node_id: str,
    *,
    fail_routes: dict[str, str] | None = None,
    sequence_action: str = "",
) -> Path:
    path = user_triage_path(project_dir)
    assert path is not None
    path.parent.mkdir(parents=True, exist_ok=True)
    data = load_yaml(path) if path.is_file() else {}
    if not isinstance(data, dict):
        data = {}
    block = data.setdefault(graph_id, {}).setdefault(node_id, {})
    if fail_routes:
        block["fail_routes"] = fail_routes
    if sequence_action:
        block["default_sequence_action"] = sequence_action
    save_yaml(path, data)
    return path


def _outcome_block(gate_spec: dict[str, Any], graph_id: str, node_id: str) -> dict[str, Any]:
    return _gate_node_block(gate_spec, graph_id, node_id).get("outcome") or {}


def _resolve_fail_class(state: dict[str, Any], outcome_block: dict[str, Any]) -> str:
    field = str(outcome_block.get("fail_class_field") or "")
    if field:
        raw = state.get(field)
        mapping = outcome_block.get("fail_class_map") or {}
        if raw in mapping:
            return str(mapping[raw])
        if str(raw) in mapping:
            return str(mapping[str(raw)])
        if raw is not None and str(raw).strip():
            return str(raw)
    return str(outcome_block.get("fail_class_default") or "unknown")


def _checks_satisfied(
    checks: list[dict[str, Any]],
    *,
    root: Path,
    graph_id: str,
    state: dict[str, Any],
    run_dir: Path,
) -> bool:
    if not checks:
        return False
    ok, _ = _eval_evidence_group(
        checks,
        ctx=_build_ctx(root, graph_id, state, run_dir),
        state=state,
        run_dir=run_dir,
        root=root,
    )
    return ok


def _build_ctx(root: Path, graph_id: str, state: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    from soc_verify.node_contract import build_contract_context

    return build_contract_context(root=root, graph_id=graph_id, state=state, run_dir=run_dir)


def evaluate_node_outcome(
    root: Path,
    graph_id: str,
    node_id: str,
    *,
    state: dict[str, Any],
    run_dir: Path | None,
) -> OutcomeResult:
    """Gate checks passed — classify pass vs fail for triage."""
    gate_spec = load_node_gate_spec(root)
    outcome_block = _outcome_block(gate_spec, graph_id, node_id)
    if not outcome_block:
        return OutcomeResult(outcome="pass", rationale_ko="no outcome spec — assume pass")

    if run_dir is None or not run_dir.is_dir():
        return OutcomeResult(outcome="unknown", rationale_ko="no run_dir")

    pass_when = list(outcome_block.get("pass_when") or [])
    fail_when = list(outcome_block.get("fail_when") or [])

    if node_id == "diagnose_env":
        if state.get("error") == "bridge_round_cap":
            return OutcomeResult(outcome="fail", fail_class="bridge_cap", rationale_ko="bridge_round_cap")
        if state.get("stalemate"):
            return OutcomeResult(outcome="fail", fail_class="stalemate", rationale_ko="stalemate")
        return OutcomeResult(outcome="pass", rationale_ko="diagnose_env completed")

    if node_id == "evaluate":
        if state.get("info_gap"):
            return OutcomeResult(outcome="fail", fail_class="info", rationale_ko="info_gap")
        if int(state.get("open_issues", 0) or 0) > 0:
            return OutcomeResult(
                outcome="fail",
                fail_class="open_issues",
                rationale_ko=f"open_issues={state.get('open_issues')}",
            )
        if state.get("verdict") == "PASS" and state.get("continue_improvement"):
            return OutcomeResult(
                outcome="fail",
                fail_class="continue_improvement",
                rationale_ko="continue_improvement after PASS",
            )
        if state.get("verdict") == "PASS":
            return OutcomeResult(outcome="pass", rationale_ko="evaluate PASS")

    if pass_when and _checks_satisfied(
        pass_when, root=root, graph_id=graph_id, state=state, run_dir=run_dir
    ):
        return OutcomeResult(outcome="pass", rationale_ko="pass_when satisfied")

    if fail_when and _checks_satisfied(
        fail_when, root=root, graph_id=graph_id, state=state, run_dir=run_dir
    ):
        fail_class = _resolve_fail_class(state, outcome_block)
        return OutcomeResult(
            outcome="fail",
            fail_class=fail_class,
            rationale_ko=f"fail_when — class={fail_class}",
        )

    if state.get("info_gap"):
        return OutcomeResult(outcome="fail", fail_class="info", rationale_ko="info_gap")
    if state.get("verdict") in ("FAIL", "BLOCKED", "INFO_GAP"):
        fc = _resolve_fail_class(state, outcome_block)
        return OutcomeResult(outcome="fail", fail_class=fc or str(state.get("verdict", "")).lower())
    if state.get("stalemate"):
        return OutcomeResult(outcome="fail", fail_class="stalemate", rationale_ko="stalemate")

    return OutcomeResult(outcome="pass", rationale_ko="default pass")


def _user_triage_block(
    project_dir: Path | None,
    graph_id: str,
    node_id: str,
    config: UserConfig | None,
) -> dict[str, Any]:
    block: dict[str, Any] = {}
    if project_dir:
        path = user_triage_path(project_dir)
        if path and path.is_file():
            data = load_yaml(path) or {}
            block.update(((data.get(graph_id) or {}).get(node_id)) or {})
    if config:
        overrides = (config.raw.get("node_triage") or {}).get(graph_id) or {}
        block.update(overrides.get(node_id) or {})
    return block


def resolve_strategy(
    root: Path,
    graph_id: str,
    node_id: str,
    *,
    outcome: OutcomeResult,
    state: dict[str, Any],
    run_dir: Path | None,
    config: UserConfig | None = None,
) -> dict[str, Any]:
    """Platform + user + LLM plan → route / sequence_action."""
    triage_spec = load_triage_spec(root)
    triage_block = _triage_node_block(triage_spec, graph_id, node_id)
    project_dir = Path(state["project_dir"]) if state.get("project_dir") else None
    user_block = _user_triage_block(project_dir, graph_id, node_id, config)

    plan = load_llm_triage_plan(run_dir, node_id) if run_dir else None

    strategy: dict[str, Any] = {"source": "platform", "route": "", "sequence_action": "", "rationale_ko": ""}

    strategy_field = triage_block.get("strategy_field")
    if strategy_field:
        action = str(state.get(strategy_field) or user_block.get("default_sequence_action") or "")
        action_routes = triage_block.get("action_routes") or {}
        if action in action_routes:
            strategy["route"] = str(action_routes[action])
            strategy["sequence_action"] = action
            strategy["rationale_ko"] = f"sequence_action={action}"
            return strategy
        if action:
            strategy["sequence_action"] = action

    if outcome.outcome == "pass":
        route = str(user_block.get("pass_route") or triage_block.get("pass_route") or "")
        strategy["route"] = route
        strategy["rationale_ko"] = outcome.rationale_ko or "outcome pass"
        return strategy

    fail_class = outcome.fail_class or "default"

    if plan and plan.get("route"):
        strategy["source"] = "llm"
        strategy["route"] = str(plan["route"])
        strategy["sequence_action"] = str(plan.get("sequence_action") or "")
        strategy["rationale_ko"] = str(plan.get("rationale_ko") or "")
        return strategy

    user_routes = user_block.get("fail_routes") or {}
    platform_routes = triage_block.get("fail_routes") or {}
    route = str(
        user_routes.get(fail_class)
        or user_routes.get("default")
        or platform_routes.get(fail_class)
        or platform_routes.get("default")
        or ""
    )
    if route:
        strategy["route"] = route
        if user_routes.get(fail_class) or user_block.get("default_sequence_action"):
            strategy["source"] = "user"
        strategy["rationale_ko"] = outcome.rationale_ko

    return strategy


def record_outcome_and_strategy(
    root: Path,
    graph_id: str,
    node_id: str,
    *,
    state: dict[str, Any],
    run_dir: Path,
    config: UserConfig | None = None,
) -> OutcomeResult:
    """Evaluate outcome, resolve strategy, persist plan when triage enabled."""
    triage_spec = load_triage_spec(root)
    triage_block = _triage_node_block(triage_spec, graph_id, node_id)
    outcome = evaluate_node_outcome(root, graph_id, node_id, state=state, run_dir=run_dir)
    strategy = resolve_strategy(
        root,
        graph_id,
        node_id,
        outcome=outcome,
        state=state,
        run_dir=run_dir,
        config=config,
    )
    outcome.strategy = strategy

    if triage_block.get("triage_enabled") and outcome.outcome == "fail" and strategy.get("route"):
        source = str(strategy.get("source", "platform"))
        if source == "platform" and not load_llm_triage_plan(run_dir, node_id):
            write_triage_plan(
                run_dir,
                node_id=node_id,
                fail_class=outcome.fail_class,
                route=strategy["route"],
                rationale_ko=strategy.get("rationale_ko") or outcome.rationale_ko,
                source=source,
                sequence_action=str(strategy.get("sequence_action") or ""),
            )
    return outcome


def _route_allowed(graph_id: str, from_node: str, to_node: str, *, root: Path) -> bool:
    if to_node == "evaluate_if_pass_else_finalize":
        return True
    spec = load_flow_spec(root)
    allowed = next_nodes_from_spec(spec, graph_id, from_node)
    return to_node in allowed or to_node == "END"


def resolve_route(
    root: Path,
    graph_id: str,
    from_node: str,
    state: dict[str, Any],
    *,
    run_dir: Path | None = None,
    config: UserConfig | None = None,
) -> str:
    """Spec-driven route for conditional edge after from_node."""
    triage_spec = load_triage_spec(root)
    triage_block = _triage_node_block(triage_spec, graph_id, from_node)
    project_dir = Path(state["project_dir"]) if state.get("project_dir") else None
    user_block = _user_triage_block(project_dir, graph_id, from_node, config)

    plan = load_llm_triage_plan(run_dir, from_node) if run_dir else None
    if plan and plan.get("route"):
        route = str(plan["route"])
        if _route_allowed(graph_id, from_node, route, root=root):
            return _normalize_special_route(route, state)

    outcome = evaluate_node_outcome(root, graph_id, from_node, state=state, run_dir=run_dir or Path("."))
    strategy = resolve_strategy(
        root, graph_id, from_node, outcome=outcome, state=state, run_dir=run_dir, config=config
    )
    route = str(strategy.get("route") or "")
    if route:
        return _normalize_special_route(route, state)

    if not triage_block:
        return ""

    if outcome.outcome == "pass":
        return str(triage_block.get("pass_route") or "")

    fail_class = outcome.fail_class or "default"
    routes = {**(triage_block.get("fail_routes") or {}), **(user_block.get("fail_routes") or {})}
    return str(routes.get(fail_class) or routes.get("default") or "")


def _normalize_special_route(route: str, state: dict[str, Any]) -> str:
    if route == "evaluate_if_pass_else_finalize":
        if state.get("verdict") == "PASS":
            return "evaluate"
        return "finalize"
    return route


def triage_payload(
    root: Path,
    graph_id: str,
    node_id: str,
    *,
    state: dict[str, Any],
    run_dir: Path | None,
    config: UserConfig | None = None,
) -> dict[str, Any]:
    triage_spec = load_triage_spec(root)
    outcome = evaluate_node_outcome(root, graph_id, node_id, state=state, run_dir=run_dir or Path("."))
    strategy = resolve_strategy(
        root, graph_id, node_id, outcome=outcome, state=state, run_dir=run_dir, config=config
    )
    block = _triage_node_block(triage_spec, graph_id, node_id)
    return {
        "contract": "node_triage_payload_v1",
        "node": node_id,
        "graph": graph_id,
        "triage_enabled": bool(block.get("triage_enabled")),
        "outcome": outcome.to_dict(),
        "strategy": strategy,
        "plan_artifact": str(triage_plan_path(run_dir, node_id)) if run_dir else "",
        "instruction_ko": (triage_spec.get("instruction_ko") or "").strip(),
    }


def enrich_sandbox_payload(payload: dict[str, Any]) -> dict[str, Any]:
    globs = list(payload.get("allowed_write_globs") or [])
    for pattern in (
        "projects/*/runs/*/node_triage/**",
        "projects/*/meta/node_triage.yaml",
    ):
        if pattern not in globs:
            globs.append(pattern)
    tools = list(payload.get("allowed_tools") or [])
    if "write_node_triage_plan" not in tools:
        tools.append("write_node_triage_plan")
    payload["allowed_write_globs"] = globs
    payload["allowed_tools"] = tools
    payload["node_triage"] = True
    return payload