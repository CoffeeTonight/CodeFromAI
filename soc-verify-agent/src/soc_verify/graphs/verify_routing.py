"""Conditional routing for verify_group LangGraph."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from soc_verify.config import UserConfig, load_user_config
from soc_verify.graphs.state import VerifyGroupState
from soc_verify.graphs.verify_helpers import run_dir as _run_dir_from_state
from soc_verify.node_triage import resolve_route


def _root_from_state(state: VerifyGroupState) -> Path:
    project_dir = state.get("project_dir")
    if project_dir:
        return Path(project_dir).parent.parent
    return Path.cwd()


def _run_dir(state: VerifyGroupState) -> Path | None:
    if state.get("project_dir") and state.get("run_id"):
        return _run_dir_from_state(state)
    return None


def _route_via_triage(
    state: VerifyGroupState,
    from_node: str,
    *,
    fallback: str,
) -> str:
    root = _root_from_state(state)
    config: UserConfig | None = None
    try:
        config = load_user_config(root)
    except FileNotFoundError:
        pass
    route = resolve_route(
        root,
        "verify_group",
        from_node,
        dict(state),
        run_dir=_run_dir(state),
        config=config,
    )
    return route or fallback


def _route_after_load_fallback(state: VerifyGroupState) -> Literal["select_runner", "finalize"]:
    if state.get("info_gap"):
        return "finalize"
    return "select_runner"


def route_after_load(state: VerifyGroupState) -> Literal["select_runner", "finalize"]:
    return _route_via_triage(state, "load_context", fallback=_route_after_load_fallback(state))  # type: ignore[return-value]


def _route_after_run_fallback(
    state: VerifyGroupState,
) -> Literal["select_runner", "evaluate", "diagnose_env", "finalize", "parse_validation_items"]:
    if state.get("info_gap") or state.get("error_kind") == "info":
        return "finalize"
    if state.get("verdict") == "PASS":
        return "evaluate"
    kind = str(state.get("error_kind", "verification"))
    if kind in ("env", "tool"):
        return "diagnose_env"
    if state.get("stalemate"):
        pattern = str(state.get("stalemate_pattern") or "").upper()
        if pattern == "OSCILLATION":
            return "parse_validation_items"
        return "finalize"
    if kind in ("verification", "none", "llm"):
        return "parse_validation_items"
    return "select_runner"


def route_after_run(
    state: VerifyGroupState,
) -> Literal["select_runner", "evaluate", "diagnose_env", "finalize", "parse_validation_items"]:
    return _route_via_triage(state, "run_gate", fallback=_route_after_run_fallback(state))  # type: ignore[return-value]


def _validation_judgment(state: VerifyGroupState) -> dict[str, Any] | None:
    run_dir = _run_dir(state)
    if not run_dir:
        judgment = state.get("validation_judgment")
        return judgment if isinstance(judgment, dict) else None
    from soc_verify.validation_autonomy import resolve_validation_judgment

    loaded = resolve_validation_judgment(
        state, run_dir, items_payload=state.get("validation_items") or {}
    )
    return loaded if isinstance(loaded, dict) and loaded else None


def _validation_sequence_action(state: VerifyGroupState) -> str:
    loaded = _validation_judgment(state)
    if isinstance(loaded, dict):
        action = str(loaded.get("sequence_action") or "")
        if action:
            return action
    action = str(state.get("validation_sequence_action") or "")
    return action or "halt"


def _route_after_apply_validation_fallback(
    state: VerifyGroupState,
) -> Literal["select_runner", "evaluate", "finalize"]:
    action = _validation_sequence_action(state)
    judgment = _validation_judgment(state)
    llm_only = frozenset({"continue_remaining", "partial_accept"})
    if action in llm_only and (
        not isinstance(judgment, dict) or str(judgment.get("source") or "") != "llm"
    ):
        action = "halt"
    if action == "retry_gate":
        return "select_runner"
    if action in ("continue_remaining", "partial_accept") and state.get("verdict") == "PASS":
        return "evaluate"
    if action in ("continue_remaining", "partial_accept"):
        return "finalize"
    if state.get("validation_continue"):
        return "finalize"
    return "finalize"


def route_after_apply_validation(
    state: VerifyGroupState,
) -> Literal["select_runner", "evaluate", "finalize"]:
    return _route_via_triage(  # type: ignore[return-value]
        state,
        "run_pending_repro",
        fallback=_route_after_apply_validation_fallback(state),
    )


def _route_after_diagnose_fallback(state: VerifyGroupState) -> Literal["patch_bridge", "finalize"]:
    if state.get("error") in ("bridge_round_cap",):
        return "finalize"
    if state.get("stalemate") and state.get("error"):
        return "finalize"
    return "patch_bridge"


def route_after_diagnose(state: VerifyGroupState) -> Literal["patch_bridge", "finalize"]:
    return _route_via_triage(state, "diagnose_env", fallback=_route_after_diagnose_fallback(state))  # type: ignore[return-value]


def _route_after_eval_fallback(
    state: VerifyGroupState,
) -> Literal["select_runner", "parity_check", "promote", "finalize"]:
    if state.get("info_gap") or state.get("error_kind") == "info":
        return "finalize"
    if int(state.get("open_issues", 0) or 0) > 0:
        return "select_runner"
    if state.get("verdict") == "PASS" and state.get("continue_improvement"):
        return "select_runner"
    if state.get("stalemate"):
        pattern = str(state.get("stalemate_pattern") or "").upper()
        if pattern == "OSCILLATION":
            return "select_runner"
        return "finalize"
    if state.get("verdict") == "PASS":
        return "parity_check"
    return "finalize"


def route_after_eval(
    state: VerifyGroupState,
) -> Literal["select_runner", "parity_check", "promote", "finalize"]:
    return _route_via_triage(state, "evaluate", fallback=_route_after_eval_fallback(state))  # type: ignore[return-value]


def _route_after_parity_fallback(state: VerifyGroupState) -> Literal["promote", "run_codegen", "finalize"]:
    if state.get("info_gap") or state.get("error_kind") == "info":
        return "finalize"
    if state.get("error") == "codegen_round_cap":
        return "finalize"
    if state.get("parity_ok"):
        return "promote"
    return "run_codegen"


def route_after_parity(state: VerifyGroupState) -> Literal["promote", "run_codegen", "finalize"]:
    return _route_via_triage(state, "parity_check", fallback=_route_after_parity_fallback(state))  # type: ignore[return-value]


def route_after_finalize(state: VerifyGroupState) -> Literal["meta_collect", "end"]:
    from soc_verify.run_profile import should_skip_meta_after_finalize

    root = _root_from_state(state)
    if should_skip_meta_after_finalize(root, state.get("run_profile")):
        return "end"
    return "meta_collect"