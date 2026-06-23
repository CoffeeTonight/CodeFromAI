"""LangGraph: main agent flow — instruct, observe, evaluate only."""

from __future__ import annotations

import json
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from soc_verify.completeness import CompletenessMetrics, evaluate_completeness_policy
from soc_verify.config import load_policies
from soc_verify.constants import (
    DEFAULT_TAU_RUN,
    EXIT_INFO_GAP,
)
from soc_verify.bridge_env import (
    apply_bridge_patch,
    build_diagnose_payload,
    write_env_diagnosis_prompt,
)
from soc_verify.bridge_env import classify_gate_failure as classify_gate_failure_kind
from soc_verify.error_classify import bump_events, classify_stop_report, resolve_bump_kind
from soc_verify.golden_library import capture_from_verdict, run_golden_suite, write_golden_report
from soc_verify.loop_guard import (
    build_signature,
    load_loop_guard,
    record_drift_score,
    record_failure,
    record_transition,
)
from soc_verify.run_spec import compute_drift, freeze_run_spec
from soc_verify.models import InfoGapError, Verdict
from soc_verify.preflight import assert_preflight, preflight_project
from soc_verify.registry_writer import apply_promotion
from soc_verify.runner import (
    append_question,
    resolve_group_script,
    run_python_script,
    write_run_metrics,
)
from soc_verify.stages import find_group_dir, is_valid_stage
from soc_verify.graphs.state import VerifyGroupState
from soc_verify.trust_eval import (
    get_trust_score,
    select_runner,
    update_trust_after_run,
    write_trust_report,
)
from soc_verify.trust_eval import evaluate_script as trust_evaluate_script
from soc_verify.erl_reflect import reflect_from_run_dir
from soc_verify.config import load_user_config
from soc_verify.crystallize import apply_crystallize_proposal
from soc_verify.graph_step import append_graph_trace, write_graph_step
from soc_verify.group_context import load_group_context, llm_brief_payload
from soc_verify.graphs.validation_nodes import (
    apply_validation_plan_node,
    parse_validation_items_node,
    run_pending_repro_node,
    validation_judge_node,
)
from soc_verify.graphs.verify_helpers import project_dir as _project_dir_from_state
from soc_verify.graphs.verify_helpers import run_dir as _run_dir_from_state
from soc_verify.graphs.verify_routing import (
    route_after_apply_validation,
    route_after_diagnose,
    route_after_eval,
    route_after_load,
    route_after_parity,
    route_after_run,
)
from soc_verify.llm_runner import (
    invoke_promote_decision,
    invoke_reproduction_finalize,
    invoke_sub_agent,
)
from soc_verify.parity_eval import (
    LLM_REFERENCE_NAME,
    parity_allows_promote,
    run_parity_check,
    snapshot_llm_reference,
    write_parity_report,
)
from soc_verify.improvement_eval import (
    append_branch_history,
    append_history,
    build_snapshot,
    collect_run_signals,
    write_improvement_signal,
    write_improvement_snapshot,
)
from soc_verify.improvement_ablation import (
    append_ablation_history,
    build_ablation_record,
    write_ablation,
)
from soc_verify.feedback_rubric import score_all_questions, write_question_quality
from soc_verify.platform_telemetry import record_platform_use
from soc_verify.experiment import register_campaign_run, resolve_experiment_tags, write_experiment_run
from soc_verify.repro_bundle import build_repro_bundle, build_repro_manifest
from soc_verify.child_graph_runtime import validate_child_after_complete
from soc_verify.branch_scorecard import (
    append_project_scorecard_history,
    build_all_branch_scorecards,
    write_branch_scorecard,
)
from soc_verify.child_graph import validate_all_child_graphs
from soc_verify.meta_graph import (
    META_PROPOSAL_NAME,
    apply_low_risk_artifacts,
    build_meta_collect_payload,
    load_meta_proposal,
    load_meta_spec,
    queue_meta_proposal,
    validate_meta_proposal,
    ensure_meta_queue_artifact,
    write_mechanical_meta_proposal,
    write_meta_collect_prompt,
)
from soc_verify.reproduction_scripts import (
    build_gate_reproduction_prompt,
    validate_gate_step,
    write_gate_reproduction_prompt,
)
from soc_verify.milestone_gate import check_milestone_gate
from soc_verify.models import load_yaml
from soc_verify.node_gate import NodeGateBlocked, finalize_node_gate, validate_node_gate
from soc_verify.tag_watch import refresh_if_due


def _project_dir(state: VerifyGroupState) -> Path:
    return _project_dir_from_state(state)


def _run_dir(state: VerifyGroupState) -> Path:
    return _run_dir_from_state(state)


def setup(state: VerifyGroupState) -> dict[str, Any]:
    run_id = state.get("run_id") or uuid.uuid4().hex[:12]
    as_of = state.get("as_of") or date.today().isoformat()
    project_dir = _project_dir(state)
    run_dir = project_dir / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    root = project_dir.parent.parent
    tags = resolve_experiment_tags(
        root,
        campaign=state.get("experiment_campaign", ""),
        condition=state.get("experiment_condition", ""),
        hypothesis=state.get("experiment_hypothesis", ""),
    )
    write_experiment_run(run_dir, tags)
    stage = state.get("stage", "")
    group = state.get("group", "")
    if stage and group:
        freeze_run_spec(
            project_dir,
            run_dir,
            stage=stage,
            group=group,
            as_of=as_of,
        )
    return {
        "run_id": run_id,
        "as_of": as_of,
        "round": 0,
        "fix_round": 0,
        "events": {
            "total_steps": 0,
            "gates_run": 0,
            "env_fail_steps": 0,
            "tool_incidents": 0,
            "info_interrupts": 0,
            "llm_fix_rounds": 0,
            "fix_rounds": 0,
            "verification_fail_steps": 0,
            "fail_fast_stops": 0,
            "max_rounds": 20,
            "one_shot": False,
        },
        "gate_results": {},
        "questions": [],
    }


def _load_context_info_gap(state: VerifyGroupState, message: str) -> dict[str, Any]:
    append_graph_trace(
        _run_dir(state),
        {"node": "load_context", "graph": "verify_group", "info_gap": True, "message": message},
    )
    return {
        "info_gap": True,
        "info_gap_message": message,
        "verdict": "INFO_GAP",
    }


def load_context(state: VerifyGroupState) -> dict[str, Any]:
    project_dir = _project_dir(state)
    gaps = preflight_project(project_dir)
    if gaps:
        return _load_context_info_gap(state, ", ".join(gaps))
    stage = state.get("stage", "")
    if not stage or not is_valid_stage(stage):
        return _load_context_info_gap(state, f"Invalid or missing stage: {stage!r}")
    root = project_dir.parent.parent
    cache = load_yaml(project_dir / "cache.yaml")
    try:
        config = load_user_config(root)
        cache, _tag_meta = refresh_if_due(project_dir, config, cache=cache)
    except FileNotFoundError:
        pass

    group_dir = find_group_dir(project_dir, stage, state["group"])
    if not group_dir:
        return _load_context_info_gap(
            state, f"Missing verification/{stage}/{state['group']}"
        )

    try:
        assert_preflight(project_dir, group_dir)
    except InfoGapError as e:
        return _load_context_info_gap(state, str(e))

    manifest = load_yaml(group_dir / "manifest.yaml")
    state_data = load_yaml(project_dir / "state.yaml")
    root = project_dir.parent.parent
    ok, msg = check_milestone_gate(manifest, state_data, root=root)
    if not ok:
        return _load_context_info_gap(state, msg)

    ctx = state.get("group_context") or load_group_context(group_dir)
    append_graph_trace(
        _run_dir(state),
        {"node": "load_context", "graph": "verify_group", "info_gap": False},
    )
    return {"info_gap": False, "group_context": ctx}


def select_runner_node(state: VerifyGroupState) -> dict[str, Any]:
    if state.get("info_gap"):
        return {}

    run_dir = _run_dir(state)
    project_dir = _project_dir(state)
    stage = state["stage"]
    group = state["group"]
    script_path = resolve_group_script(project_dir, stage, group)
    script_name = script_path.name if script_path else f"{group}.py"

    loop = load_loop_guard(run_dir)
    force = state.get("force_mode") or (loop.force_mode if loop.stalemate else "")
    if loop.stalemate or force:
        mode = force or "llm_full"
        out = {"runner": "llm", "script_name": script_name, "force_mode": mode}
        if loop.stalemate_pattern:
            out["stalemate_pattern"] = loop.stalemate_pattern
        append_graph_trace(run_dir, {"node": "select_runner", **out})
        record_transition(run_dir, "select_runner", error_kind=loop.stalemate_pattern or mode)
        return out

    meta = {}
    meta_path = project_dir / "meta.yaml"
    if meta_path.is_file():
        import yaml

        meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}

    tau = float(meta.get("tau_run", DEFAULT_TAU_RUN))
    tau_c = float(meta.get("tau_completeness_run", 0.75))
    # First round: no prior C → trust only. After evaluate, low C → llm.
    prior_c = state.get("completeness")
    completeness_arg = float(prior_c) if prior_c is not None and state.get("round", 0) > 0 else None

    runner = select_runner(
        project_dir,
        script_name,
        tau,
        completeness=completeness_arg,
        tau_completeness=tau_c,
    )
    if runner == "python":
        runner_mode = "python_canonical"
    else:
        runner_mode = str(state.get("runner_mode") or "llm_tools")
    out = {
        "runner": runner,
        "runner_mode": runner_mode,
        "script_name": script_name,
        "round": state.get("round", 0) + 1,
    }
    append_graph_trace(
        run_dir,
        {"node": "select_runner", "runner": runner, "runner_mode": runner_mode},
    )
    return out


def run_gate(state: VerifyGroupState) -> dict[str, Any]:
    if state.get("info_gap"):
        return {}

    project_dir = _project_dir(state)
    run_dir = _run_dir(state)
    group = state["group"]
    events = dict(state.get("events", {}))
    events["gates_run"] = int(events.get("gates_run", 0)) + 1

    if state.get("runner") == "llm":
        ctx = state.get("group_context") or {}
        stage = state["stage"]
        runner_mode = str(state.get("runner_mode") or "llm_tools")
        step_path = write_graph_step(
            run_dir,
            graph="verify_group",
            node="run_gate",
            group=group,
            stage=stage,
            runner="llm",
            fix_round=int(state.get("fix_round", 0)),
            orchestrator_run_id=state.get("orchestrator_run_id", ""),
            extra={
                "runner_mode": runner_mode,
                "runner_loop_diagram": "templates/obsidian/08-RUNNER-LOOP.md",
                "mandatory_rules": [
                    "llm_tools: tool calling until verdict PASS (CHECK.md)",
                    "Do not promote without parity_report.ok",
                ],
            },
        )
        brief = llm_brief_payload(
            graph="verify_group",
            node="run_gate",
            group_context=ctx,
            extra={
                "orchestrator_run_id": state.get("orchestrator_run_id"),
                "run_id": state.get("run_id"),
                "project_id": state.get("project_id"),
                "graph_step_file": str(step_path),
                "md_only_prompt_file": str(run_dir / "md_only_prompt.json"),
            },
        )
        (run_dir / "llm_brief.json").write_text(
            json.dumps(brief, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        root = project_dir.parent.parent
        try:
            config = load_user_config(root)
        except FileNotFoundError:
            config = None

        llm_result = invoke_sub_agent(
            run_dir,
            group_context=ctx,
            graph_step_path=step_path,
            root=root,
            config=config,
        )
        append_graph_trace(
            run_dir,
            {
                "node": "run_gate",
                "runner": "llm",
                "llm_mode": llm_result.mode,
                "llm_message": llm_result.message,
            },
        )

        verdict_path = run_dir / f"verdict_{group}.json"
        if llm_result.verdict is not None:
            v = llm_result.verdict
            gate_results = dict(state.get("gate_results", {}))
            gate_results[group] = v.status
            passed = v.status == "PASS"
            kind = classify_gate_failure_kind(verdict=v, sub_stop=None)
            if passed:
                events["one_shot"] = state.get("fix_round", 0) == 0
            else:
                events = bump_events(events, resolve_bump_kind(kind))
            out: dict[str, Any] = {
                "gate_results": gate_results,
                "verdict": v.status,
                "events": events,
                "error_kind": kind,
            }
            if not passed:
                out["fix_round"] = state.get("fix_round", 0) + 1
            return out

        if verdict_path.is_file():
            data = json.loads(verdict_path.read_text(encoding="utf-8"))
            v = Verdict.from_dict(data)
            gate_results = dict(state.get("gate_results", {}))
            gate_results[group] = v.status
            kind = classify_gate_failure_kind(verdict=v, sub_stop=None)
            out = {
                "gate_results": gate_results,
                "verdict": v.status,
                "events": events,
                "error_kind": kind,
            }
            if v.status != "PASS":
                events = bump_events(events, resolve_bump_kind(kind))
                out["events"] = events
                out["fix_round"] = state.get("fix_round", 0) + 1
            return out

        # Sub-agent slot: expect sub_stop.json or verdict written externally
        stop_path = run_dir / "sub_stop.json"
        if stop_path.is_file():
            sub_stop = json.loads(stop_path.read_text(encoding="utf-8"))
            events["fail_fast_stops"] = int(events.get("fail_fast_stops", 0)) + 1
            kind = classify_stop_report(sub_stop)
            events = bump_events(events, kind)
            sig = build_signature(stop=sub_stop)
            loop = record_failure(run_dir, sig)
            loop = record_transition(run_dir, "run_gate", error_kind=kind)
            partial = str(sub_stop.get("partial_verdict", "FAIL"))
            out_stop: dict[str, Any] = {
                "sub_stop": sub_stop,
                "events": events,
                "verdict": partial,
                "error_kind": kind,
                "stalemate": loop.stalemate,
                "force_mode": loop.force_mode if loop.stalemate else "",
                "fix_round": state.get("fix_round", 0) + 1,
            }
            if loop.stalemate_pattern:
                out_stop["stalemate_pattern"] = loop.stalemate_pattern
            return out_stop
        # LLM mode without artifact → FAIL (sub must write sub_stop or verdict)
        events = bump_events(events, "llm")
        return {
            "events": events,
            "verdict": "FAIL",
            "error": "llm_runner_awaiting_sub_agent",
            "error_kind": "llm",
            "fix_round": state.get("fix_round", 0) + 1,
        }

    stage = state["stage"]
    script_path = resolve_group_script(project_dir, stage, group)
    if script_path is None:
        return {
            "info_gap": True,
            "info_gap_message": f"No script for {stage}/{group}",
            "verdict": "INFO_GAP",
        }

    root = project_dir.parent.parent
    write_graph_step(
        run_dir,
        graph="verify_group",
        node="run_gate",
        group=group,
        stage=stage,
        runner="python",
        fix_round=int(state.get("fix_round", 0)),
        orchestrator_run_id=state.get("orchestrator_run_id", ""),
        root=root,
    )

    try:
        verdict = run_python_script(
            script_path,
            project_dir=project_dir,
            run_dir=run_dir,
            gate=group,
        )
    except InfoGapError as e:
        events = bump_events(events, "info")
        return {
            "info_gap": True,
            "info_gap_message": str(e),
            "verdict": "INFO_GAP",
            "events": events,
        }

    tag = ""
    cache_path = project_dir / "cache.yaml"
    if cache_path.is_file():
        import yaml

        cache = yaml.safe_load(cache_path.read_text(encoding="utf-8")) or {}
        tag = (cache.get("tag") or {}).get("value", "")

    passed = verdict.status == "PASS"
    one_shot = state.get("fix_round", 0) == 0 and passed
    if one_shot:
        events["one_shot"] = True

    score = update_trust_after_run(
        project_dir,
        state.get("script_name", script_path.name),
        passed=passed,
        one_shot=one_shot,
        tag=tag,
    )

    gate_results = dict(state.get("gate_results", {}))
    gate_results[group] = verdict.status

    if not passed:
        fail_kind = classify_gate_failure_kind(verdict=verdict, sub_stop=None)
        bump_kind = resolve_bump_kind(fail_kind, exit_code=verdict.exit_code)
        events = bump_events(events, bump_kind)
        sig = build_signature(verdict=verdict)
        loop = record_failure(run_dir, sig)
        loop = record_transition(run_dir, "run_gate", error_kind=fail_kind)
        append_graph_trace(
            run_dir,
            {
                "node": "run_gate",
                "runner": "python",
                "verdict": verdict.status,
                "error_kind": fail_kind,
            },
        )
        out_fail: dict[str, Any] = {
            "gate_results": gate_results,
            "trust_score": score,
            "verdict": verdict.status,
            "events": events,
            "error_kind": fail_kind,
            "stalemate": loop.stalemate,
            "force_mode": loop.force_mode if loop.stalemate else "",
            "fix_round": state.get("fix_round", 0) + 1,
        }
        if loop.stalemate_pattern:
            out_fail["stalemate_pattern"] = loop.stalemate_pattern
        return out_fail

    append_graph_trace(
        run_dir,
        {"node": "run_gate", "runner": "python", "verdict": "PASS", "error_kind": "none"},
    )
    return {
        "gate_results": gate_results,
        "trust_score": score,
        "verdict": "PASS",
        "events": events,
        "error_kind": "none",
    }


def evaluate_node(state: VerifyGroupState) -> dict[str, Any]:
    if state.get("info_gap"):
        return {"verdict": "INFO_GAP"}

    project_dir = _project_dir(state)
    run_dir = _run_dir(state)
    stage = state["stage"]
    group = state["group"]
    verdict = str(state.get("verdict", "FAIL"))

    validation_items = state.get("validation_items")
    if not validation_items and (run_dir / "validation_items.json").is_file():
        validation_items = json.loads((run_dir / "validation_items.json").read_text(encoding="utf-8"))

    root = project_dir.parent.parent
    try:
        policies = load_policies(root)
    except Exception:
        policies = {}

    drift_max = float((policies.get("drift") or {}).get("max", 0.3))
    drift_report = compute_drift(
        project_dir,
        run_dir,
        stage=stage,
        group=group,
        validation_items=validation_items,
        drift_max=drift_max,
    )
    record_drift_score(run_dir, float(drift_report.get("drift_score", 0.0)))

    block_pass = bool((policies.get("drift") or {}).get("block_pass_when_exceeded", True))
    if verdict == "PASS" and block_pass and not drift_report.get("ok", True):
        verdict = "FAIL"

    open_issues = 0 if verdict == "PASS" else 1

    events = dict(state.get("events", {}))
    metrics = CompletenessMetrics.from_events(events)
    write_run_metrics(run_dir, metrics.to_dict())

    script_name = str(state.get("script_name", ""))
    trust_runs = 0
    if script_name:
        reg = load_yaml(project_dir / "trust" / "registry.yaml")
        rec = (reg.get("scripts") or {}).get(script_name) or {}
        trust_runs = int(rec.get("runs", 0))

    decision = evaluate_completeness_policy(
        metrics,
        policies,
        verdict=verdict,
        trust_score=float(state.get("trust_score", 0.0)),
        trust_runs=trust_runs,
    )
    (run_dir / "completeness_decision.json").write_text(
        json.dumps(decision.to_dict(), indent=2),
        encoding="utf-8",
    )

    if verdict == "PASS":
        verdict_path = run_dir / f"verdict_{group}.json"
        if verdict_path.is_file():
            vdata = json.loads(verdict_path.read_text(encoding="utf-8"))
            cache = load_yaml(project_dir / "cache.yaml")
            tag = str((cache.get("tag") or {}).get("value") or "")
            capture_from_verdict(
                project_dir,
                stage=stage,
                group=group,
                tag=tag,
                verdict=vdata,
                run_id=str(state.get("run_id", run_dir.name)),
            )

    out: dict[str, Any] = {
        "open_issues": open_issues,
        "verdict": verdict,
        "completeness": metrics.score,
        "jira_allowed": decision.jira_allowed,
        "continue_improvement": decision.continue_improvement,
        "drift_score": drift_report.get("drift_score", 0.0),
        "drift_ok": drift_report.get("ok", True),
    }
    return out


def diagnose_env_node(state: VerifyGroupState) -> dict[str, Any]:
    """LLM diagnoses env/tool execution failures — does not change CHECK criteria."""
    if state.get("info_gap"):
        return {}

    project_dir = _project_dir(state)
    run_dir = _run_dir(state)
    stage = state["stage"]
    group = state["group"]
    ctx = state.get("group_context") or {}

    root = project_dir.parent.parent
    try:
        policies = load_policies(root)
    except Exception:
        policies = {}
    max_rounds = int((policies.get("bridge_loop") or {}).get("max_bridge_rounds", 8))
    round_n = int(state.get("bridge_round", 0))
    if round_n >= max_rounds:
        return {
            "verdict": "FAIL",
            "error": "bridge_round_cap",
            "questions": [
                {
                    "id": f"Q-bridge-cap-{state['run_id']}",
                    "type": "bridge",
                    "context": f"{stage}/{group}",
                    "question": f"env/bridge loop cap after {max_rounds} rounds",
                    "blocking": "no",
                }
            ],
        }

    verdict_data = None
    verdict_path = run_dir / f"verdict_{group}.json"
    if verdict_path.is_file():
        verdict_data = json.loads(verdict_path.read_text(encoding="utf-8"))

    payload = build_diagnose_payload(
        project_dir=project_dir,
        stage=stage,
        group=group,
        run_dir=run_dir,
        error_kind=str(state.get("error_kind", "env")),
        verdict=verdict_data,
        sub_stop=state.get("sub_stop"),
    )
    write_env_diagnosis_prompt(run_dir, payload)

    step_path = write_graph_step(
        run_dir,
        graph="verify_group",
        node="diagnose_env",
        group=group,
        stage=stage,
        runner="llm",
        fix_round=int(state.get("fix_round", 0)),
        orchestrator_run_id=state.get("orchestrator_run_id", ""),
        extra={
            "runner_mode": "llm_diagnose_env",
            "bridge_loop_diagram": "templates/obsidian/09-BRIDGE-LOOP.md",
            "required_artifacts": ["env_diagnosis.md", "bridge_patch_proposal.md"],
            "instruction": payload["instruction"],
        },
    )

    root_cfg = root
    try:
        config = load_user_config(root_cfg)
    except FileNotFoundError:
        config = None

    invoke_sub_agent(
        run_dir,
        group_context=ctx,
        graph_step_path=step_path,
        root=root_cfg,
        config=config,
    )

    templates_root = root / "templates"
    for name, tpl in (
        ("env_diagnosis.md", "env_diagnosis.md"),
        ("bridge_patch_proposal.md", "bridge_patch_proposal.md"),
    ):
        dst = run_dir / name
        src = templates_root / tpl
        if not dst.is_file() and src.is_file():
            text = src.read_text(encoding="utf-8")
            text = text.replace("{{stage}}", stage).replace("{{group}}", group)
            dst.write_text(text, encoding="utf-8")

    append_graph_trace(run_dir, {"node": "diagnose_env", "error_kind": state.get("error_kind")})
    record_transition(run_dir, "diagnose_env", error_kind=str(state.get("error_kind", "env")))
    return {"runner": "llm", "runner_mode": "llm_diagnose_env", "error": ""}


def patch_bridge_node(state: VerifyGroupState) -> dict[str, Any]:
    """Apply bridge/*.py + environment_profile from LLM proposal; retry run_gate."""
    project_dir = _project_dir(state)
    run_dir = _run_dir(state)
    stage = state["stage"]
    group = state["group"]

    outcome = apply_bridge_patch(project_dir, stage, group, run_dir, force=True)
    append_graph_trace(
        run_dir,
        {"node": "patch_bridge", "applied": outcome.get("applied"), "reason": outcome.get("reason", "")},
    )
    record_transition(
        run_dir,
        "patch_bridge",
        error_kind="applied" if outcome.get("applied") else "not_applied",
        next_node="select_runner",
    )

    out: dict[str, Any] = {
        "bridge_round": int(state.get("bridge_round", 0)) + 1,
        "bridge_outcome": outcome,
    }
    if not outcome.get("applied"):
        out["error"] = "bridge_patch_not_applied"
        out["questions"] = [
            {
                "id": f"Q-bridge-{state['run_id']}",
                "type": "bridge",
                "context": f"{stage}/{group}",
                "question": f"bridge patch failed: {outcome.get('reason', 'unknown')}",
                "blocking": "no",
            }
        ]
    else:
        out["error"] = ""
    return out


def promote_node(state: VerifyGroupState) -> dict[str, Any]:
    project_dir = _project_dir(state)
    run_dir = _run_dir(state)
    script_name = state.get("script_name", "")
    root = project_dir.parent.parent

    if script_name:
        script_path = resolve_group_script(project_dir, state["stage"], state["group"])
        if script_path and script_path.is_file():
            golden_report = run_golden_suite(project_dir, script_path)
            write_golden_report(run_dir, golden_report)
            result = trust_evaluate_script(project_dir, script_path)
            write_trust_report(run_dir, result)
            comp_path = run_dir / "completeness_decision.json"
            comp_dec = None
            if comp_path.is_file():
                comp_dec = json.loads(comp_path.read_text(encoding="utf-8"))

            try:
                config = load_user_config(root)
            except FileNotFoundError:
                config = None

            invoke_promote_decision(
                run_dir,
                script_name=script_name,
                trust_report=result.to_dict(),
                root=root,
                config=config,
            )

            outcome = apply_promotion(
                project_dir,
                script_name,
                trust_score=result.trust_score,
                run_dir=run_dir,
                completeness_decision=comp_dec,
            )

            crystallize_out: dict[str, Any] = {"applied": False}
            if outcome.get("promoted"):
                crystallize_out = apply_crystallize_proposal(
                    project_dir,
                    state["stage"],
                    state["group"],
                    run_dir,
                )
                outcome["crystallize"] = crystallize_out

            append_graph_trace(
                run_dir,
                {
                    "node": "promote",
                    "promoted": outcome.get("promoted"),
                    "crystallize": crystallize_out,
                },
            )
            child_ev = validate_child_after_complete(
                root,
                "verify_group",
                "promote",
                state=dict(state),
                run_dir=run_dir,
            )
            if not child_ev.ok:
                return {
                    "promote_outcome": outcome,
                    "trust_score": result.trust_score,
                    "child_evidence_blocked": child_ev.to_dict(),
                }
            return {"promote_outcome": outcome, "trust_score": result.trust_score}

    return {}


def parity_check_node(state: VerifyGroupState) -> dict[str, Any]:
    """Platform: compare llm_reference vs Python ops — mandatory before promote."""
    if state.get("verdict") != "PASS":
        return {}

    project_dir = _project_dir(state)
    run_dir = _run_dir(state)
    stage = state["stage"]
    group = state["group"]

    if state.get("runner") == "python":
        write_parity_report(
            run_dir,
            {
                "ok": True,
                "skipped": "python_canonical",
                "issues": [],
                "contract": "parity_eval_v1",
            },
        )
        append_graph_trace(run_dir, {"node": "parity_check", "skipped": "python_canonical"})
        return {"parity_ok": True}

    ref_path = run_dir / LLM_REFERENCE_NAME
    if not ref_path.is_file():
        snapshot_llm_reference(run_dir, group)

    script_path = resolve_group_script(project_dir, stage, group)
    if script_path is None or not script_path.is_file():
        append_graph_trace(run_dir, {"node": "parity_check", "ok": False, "reason": "no_ops"})
        return {"parity_ok": False, "runner": "llm", "runner_mode": "llm_codegen"}

    try:
        py_verdict = run_python_script(
            script_path,
            project_dir=project_dir,
            run_dir=run_dir,
            gate=group,
        )
    except InfoGapError as e:
        return {
            "parity_ok": False,
            "runner": "llm",
            "runner_mode": "llm_codegen",
            "info_gap_message": str(e),
        }

    report = run_parity_check(run_dir, group, python_verdict=py_verdict.to_dict())
    ok = bool(report.get("ok"))
    append_graph_trace(run_dir, {"node": "parity_check", "ok": ok, "issues": report.get("issues", [])})

    if ok:
        return {"parity_ok": True}
    return {
        "parity_ok": False,
        "runner": "llm",
        "runner_mode": "llm_codegen",
        "codegen_round": int(state.get("codegen_round", 0)) + 1,
    }


def run_codegen_node(state: VerifyGroupState) -> dict[str, Any]:
    """LLM writes/fixes ops/*.py — only after llm_tools PASS; parity fail = ops bug."""
    project_dir = _project_dir(state)
    run_dir = _run_dir(state)
    group = state["group"]
    stage = state["stage"]
    ctx = state.get("group_context") or {}

    root = project_dir.parent.parent
    try:
        policies = load_policies(root)
    except Exception:
        policies = {}
    max_rounds = int((policies.get("runner_contract") or {}).get("max_codegen_rounds", 10))
    round_n = int(state.get("codegen_round", 0))
    if round_n >= max_rounds:
        return {
            "verdict": "FAIL",
            "error": "codegen_round_cap",
            "questions": [
                {
                    "id": f"Q-codegen-cap-{state['run_id']}",
                    "type": "codegen",
                    "context": f"{stage}/{group}",
                    "question": f"parity not reached after {max_rounds} codegen rounds",
                    "blocking": "no",
                }
            ],
        }

    script_path = resolve_group_script(project_dir, stage, group)
    parity_ok, parity_reason = parity_allows_promote(run_dir)

    step_path = write_graph_step(
        run_dir,
        graph="verify_group",
        node="run_codegen",
        group=group,
        stage=stage,
        runner="llm",
        fix_round=round_n,
        orchestrator_run_id=state.get("orchestrator_run_id", ""),
        extra={
            "runner_mode": "llm_codegen",
            "runner_loop_diagram": "templates/obsidian/08-RUNNER-LOOP.md",
            "required_artifacts": [
                f"ops/{stage}/{group}.py",
            ],
            "parity_reason": parity_reason,
            "llm_reference": str(run_dir / LLM_REFERENCE_NAME),
            "instruction": (
                "Write or fix ops Python so it matches llm_reference_verdict.json. "
                "Python mismatch is an ops bug, not spec change."
            ),
        },
    )

    payload = {
        "contract": "run_codegen",
        "ops_target": str(script_path or project_dir / "ops" / stage / f"{group}.py"),
        "llm_reference": str(run_dir / LLM_REFERENCE_NAME),
        "parity_report": str(run_dir / "parity_report.json"),
        "graph_step": str(step_path),
    }
    (run_dir / "codegen_prompt.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    try:
        config = load_user_config(root)
    except FileNotFoundError:
        config = None

    invoke_sub_agent(
        run_dir,
        group_context=ctx,
        graph_step_path=step_path,
        root=root,
        config=config,
    )
    append_graph_trace(run_dir, {"node": "run_codegen", "round": round_n})
    return {"runner": "llm", "runner_mode": "llm_codegen", "codegen_round": round_n}


def finalize_reproduction_node(state: VerifyGroupState) -> dict[str, Any]:
    """After PASS+promote: ensure step script + verification_sequence entry exist."""
    if state.get("verdict") != "PASS":
        return {}

    project_dir = _project_dir(state)
    run_dir = _run_dir(state)
    stage = state["stage"]
    group = state["group"]
    run_id = state["run_id"]

    write_graph_step(
        run_dir,
        graph="verify_group",
        node="finalize_reproduction",
        group=group,
        stage=stage,
        runner=state.get("runner", "python"),
        fix_round=int(state.get("fix_round", 0)),
        orchestrator_run_id=state.get("orchestrator_run_id", ""),
        extra={
            "required_artifacts": [
                f"scripts/NN_{stage}_*.sh",
                "scripts/verification_sequence.yaml",
                "reproduction_finalize.json",
            ],
            "rules_template": "templates/scripts/README.md",
        },
    )

    payload = build_gate_reproduction_prompt(
        project_dir=project_dir,
        stage=stage,
        group=group,
        run_id=run_id,
        verdict_path=str(run_dir / f"verdict_{group}.json"),
    )
    write_gate_reproduction_prompt(run_dir, payload)

    root = project_dir.parent.parent
    try:
        config = load_user_config(root)
    except FileNotFoundError:
        config = None

    invoke_reproduction_finalize(run_dir, payload=payload, root=root, config=config)

    validation = validate_gate_step(project_dir, stage, group)
    append_graph_trace(
        run_dir,
        {
            "node": "finalize_reproduction",
            "validation_ok": validation["ok"],
            "issues": validation.get("issues", []),
        },
    )

    out: dict[str, Any] = {"reproduction_validation": validation}
    if not validation["ok"]:
        out["questions"] = [
            {
                "id": f"Q-repro-{run_id}",
                "type": "reproduction",
                "context": f"{stage}/{group}",
                "question": (
                    "Reproduction step script or verification_sequence.yaml incomplete: "
                    + "; ".join(validation.get("issues", []))
                ),
                "blocking": "no",
            }
        ]
    return out


def finalize_node(state: VerifyGroupState) -> dict[str, Any]:
    project_dir = _project_dir(state)
    run_dir = _run_dir(state)
    events = dict(state.get("events", {}))
    metrics = CompletenessMetrics.from_events(events)
    if not (run_dir / "metrics.json").is_file():
        write_run_metrics(run_dir, metrics.to_dict())

    questions: list[dict[str, Any]] = list(state.get("questions", []))

    if state.get("info_gap"):
        q = {
            "id": f"Q-info-{state['run_id']}",
            "type": "info",
            "context": state.get("group", ""),
            "question": state.get("info_gap_message", ""),
            "blocking": "yes",
        }
        append_question(project_dir, q)
        questions.append(q)

    loop = load_loop_guard(run_dir)
    if loop.stalemate:
        q = {
            "id": f"Q-stale-{state['run_id']}",
            "type": "stalemate",
            "context": state.get("group", ""),
            "question": "Same failure signature repeated; review logs and provide guidance.",
            "blocking": "no",
        }
        append_question(project_dir, q)
        questions.append(q)

    reflect_from_run_dir(project_dir, run_dir, state.get("group", ""))

    append_graph_trace(
        run_dir,
        {
            "node": "finalize",
            "graph": "verify_group",
            "verdict": state.get("verdict"),
            "info_gap": bool(state.get("info_gap")),
        },
    )

    return {
        "completeness": metrics.score,
        "questions": questions,
        "jira_allowed": state.get("jira_allowed", False),
        "continue_improvement": state.get("continue_improvement", False),
    }


def meta_collect_node(state: VerifyGroupState) -> dict[str, Any]:
    """Gather run signals + change hints for meta-graph (platform)."""
    project_dir = _project_dir(state)
    run_dir = _run_dir(state)
    root = project_dir.parent.parent
    state_dict = dict(state)
    child_summary = validate_all_child_graphs(
        root, "verify_group", state=state_dict, run_dir=run_dir
    )
    scorecard = build_all_branch_scorecards(
        root,
        project_dir,
        run_dir,
        state_dict,
        child_summary=child_summary,
    )
    write_branch_scorecard(run_dir, scorecard)
    append_project_scorecard_history(project_dir, scorecard)

    signals = collect_run_signals(run_dir, state_dict)
    write_improvement_signal(run_dir, signals)
    snapshot = build_snapshot(project_dir, run_dir, signals, as_of=state.get("as_of"))
    write_improvement_snapshot(run_dir, snapshot)
    payload = build_meta_collect_payload(
        root=root,
        project_dir=project_dir,
        run_dir=run_dir,
        signals=signals,
        snapshot=snapshot.to_dict(),
        state=dict(state),
    )
    write_meta_collect_prompt(run_dir, payload)
    append_graph_trace(run_dir, {"node": "meta_collect", "improvement_index": snapshot.improvement_index})
    return {"improvement_index": snapshot.improvement_index}


def meta_score_node(state: VerifyGroupState) -> dict[str, Any]:
    """Persist KPI time series — platform only."""
    project_dir = _project_dir(state)
    run_dir = _run_dir(state)
    root = project_dir.parent.parent
    state_dict = dict(state)
    sig_path = run_dir / "improvement_signal.json"
    snap_dict: dict[str, Any] = {}
    if sig_path.is_file():
        signals = json.loads(sig_path.read_text(encoding="utf-8"))
        snap = build_snapshot(project_dir, run_dir, signals, as_of=state.get("as_of"))
        append_history(project_dir, snap)
        snap_dict = snap.to_dict()

    sc_path = run_dir / "branch_scorecard.json"
    scorecard: dict[str, Any] = {}
    if sc_path.is_file():
        scorecard = json.loads(sc_path.read_text(encoding="utf-8"))
        append_branch_history(
            project_dir,
            run_id=str(state.get("run_id", run_dir.name)),
            stage=str(state.get("stage", "")),
            group=str(state.get("group", "")),
            branch_scorecard=scorecard,
        )

    if snap_dict:
        ablation = build_ablation_record(
            project_dir,
            run_dir,
            run_id=str(state.get("run_id", run_dir.name)),
            stage=str(state.get("stage", "")),
            group=str(state.get("group", "")),
            snapshot=snap_dict,
            branch_scorecard=scorecard or None,
        )
        write_ablation(run_dir, ablation)
        append_ablation_history(project_dir, ablation)

    qq = score_all_questions(list(state.get("questions") or []))
    write_question_quality(run_dir, qq)

    branches = scorecard.get("branches") or []
    mean_success = None
    if branches:
        mean_success = sum(float(b.get("success_rate", 0)) for b in branches) / len(branches)

    record_platform_use(
        root,
        kind="verify_group_complete",
        graph_id="verify_group",
        run_id=str(state.get("run_id", run_dir.name)),
        verdict=str(state.get("verdict", "UNKNOWN")),
        trust_score=float(state.get("trust_score", 0.0)) or None,
        success_rate=mean_success,
        project_id=str(state.get("project_id", "")),
        stage=str(state.get("stage", "")),
        group=str(state.get("group", "")),
        extra={"improvement_index": state.get("improvement_index"), "question_sharpness": qq.get("mean_sharpness")},
    )

    purpose = f"verify_group {state.get('stage')}/{state.get('group')} verdict={state.get('verdict')}"
    manifest = build_repro_manifest(
        root,
        run_dir=run_dir,
        project_dir=project_dir,
        purpose=purpose,
        graph_id="verify_group",
        run_id=str(state.get("run_id", run_dir.name)),
        state=state_dict,
    )
    build_repro_bundle(root, run_dir, manifest)

    exp = resolve_experiment_tags(
        root,
        campaign=state.get("experiment_campaign", ""),
        condition=state.get("experiment_condition", ""),
        hypothesis=state.get("experiment_hypothesis", ""),
    )
    register_campaign_run(
        root,
        exp,
        run_meta={
            "run_id": str(state.get("run_id", run_dir.name)),
            "graph_id": "verify_group",
            "project_id": str(state.get("project_id", "")),
            "stage": str(state.get("stage", "")),
            "group": str(state.get("group", "")),
            "verdict": str(state.get("verdict", "")),
            "improvement_index": state.get("improvement_index"),
        },
    )

    append_graph_trace(run_dir, {"node": "meta_score", "index": state.get("improvement_index")})
    return {}


def meta_propose_node(state: VerifyGroupState) -> dict[str, Any]:
    """LLM proposes structured changes — meta_change_proposal.json."""
    project_dir = _project_dir(state)
    run_dir = _run_dir(state)
    root = project_dir.parent.parent
    stage = state["stage"]
    group = state["group"]
    ctx = state.get("group_context") or {}

    step_path = write_graph_step(
        run_dir,
        graph="verify_group",
        node="meta_propose",
        group=group,
        stage=stage,
        runner="llm",
        fix_round=int(state.get("fix_round", 0)),
        orchestrator_run_id=state.get("orchestrator_run_id", ""),
        extra={
            "meta_graph_spec": "registry/meta_graph_spec.yaml",
            "meta_graph_diagram": "templates/obsidian/10-META-GRAPH.md",
            "langgraph_summary": "templates/obsidian/11-LANGGRAPH-SUMMARY.md",
            "required_artifacts": ["meta_change_proposal.json"],
            "reads": ["meta_collect_prompt.json", "improvement_snapshot.json"],
        },
    )

    tpl = root / "templates" / "meta_change_proposal.md"
    if tpl.is_file() and not (run_dir / "meta_change_proposal.md").is_file():
        text = tpl.read_text(encoding="utf-8")
        for key in ("run_id", "project_id", "stage", "group"):
            text = text.replace(f"{{{{{key}}}}}", str(state.get(key, state.get("project_id", ""))))
        (run_dir / "meta_change_proposal.md").write_text(text, encoding="utf-8")

    try:
        config = load_user_config(root)
    except FileNotFoundError:
        config = None

    llm_result = invoke_sub_agent(
        run_dir,
        group_context=ctx,
        graph_step_path=step_path,
        root=root,
        config=config,
    )
    proposal_path = run_dir / META_PROPOSAL_NAME
    if not proposal_path.is_file():
        write_mechanical_meta_proposal(
            run_dir,
            run_id=str(state.get("run_id", run_dir.name)),
            stage=stage,
            group=group,
            root=root,
        )
    else:
        try:
            existing = json.loads(proposal_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
        if not (existing.get("changes") or []):
            write_mechanical_meta_proposal(
                run_dir,
                run_id=str(state.get("run_id", run_dir.name)),
                stage=stage,
                group=group,
                root=root,
            )

    ensure_meta_queue_artifact(project_dir, run_dir, root=root)
    append_graph_trace(run_dir, {"node": "meta_propose"})
    return {"runner": "llm", "runner_mode": "llm_meta_propose"}


def meta_queue_node(state: VerifyGroupState) -> dict[str, Any]:
    """Validate proposal, queue patches — never auto-apply graph_source."""
    project_dir = _project_dir(state)
    run_dir = _run_dir(state)
    root = project_dir.parent.parent
    spec = load_meta_spec(root)

    proposal = load_meta_proposal(run_dir)
    if proposal is None:
        stub = {
            "queued_at": date.today().isoformat(),
            "run_id": state.get("run_id", run_dir.name),
            "validation": {"ok": False, "issues": ["no_meta_change_proposal"]},
            "proposal": None,
            "status": "skipped",
        }
        (run_dir / "meta_change_queued.json").write_text(
            json.dumps(stub, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        append_graph_trace(run_dir, {"node": "meta_queue", "queued": False, "reason": "no_proposal"})
        return {"meta_queued": False}

    validation = validate_meta_proposal(proposal, spec)
    outcome = queue_meta_proposal(project_dir, run_dir, proposal, validation)

    apply_result: dict[str, Any] = {"applied": [], "skipped": []}
    try:
        policies = load_policies(root)
    except Exception:
        policies = {}
    if validation.get("ok") and (policies.get("meta_graph") or {}).get("auto_apply_low_risk"):
        apply_result = apply_low_risk_artifacts(
            project_dir, proposal, spec, policies=policies
        )

    append_graph_trace(
        run_dir,
        {
            "node": "meta_queue",
            "queued": outcome.get("queued"),
            "validation_ok": validation.get("ok"),
            "applied": apply_result.get("applied"),
        },
    )
    return {
        "meta_queued": bool(outcome.get("queued")),
        "meta_queue_path": outcome.get("path"),
    }


_VERIFY_NODES = (
    "setup",
    "load_context",
    "select_runner",
    "run_gate",
    "parse_validation_items",
    "validation_judge",
    "apply_validation_plan",
    "run_pending_repro",
    "diagnose_env",
    "patch_bridge",
    "evaluate",
    "parity_check",
    "run_codegen",
    "promote",
    "finalize_reproduction",
    "finalize",
    "meta_collect",
    "meta_score",
    "meta_propose",
    "meta_queue",
)


def _build_verify_group_state_graph() -> StateGraph:
    g = StateGraph(VerifyGroupState)
    g.add_node("setup", setup)
    g.add_node("load_context", load_context)
    g.add_node("select_runner", select_runner_node)
    g.add_node("run_gate", run_gate)
    g.add_node("parse_validation_items", parse_validation_items_node)
    g.add_node("validation_judge", validation_judge_node)
    g.add_node("apply_validation_plan", apply_validation_plan_node)
    g.add_node("run_pending_repro", run_pending_repro_node)
    g.add_node("diagnose_env", diagnose_env_node)
    g.add_node("patch_bridge", patch_bridge_node)
    g.add_node("evaluate", evaluate_node)
    g.add_node("parity_check", parity_check_node)
    g.add_node("run_codegen", run_codegen_node)
    g.add_node("promote", promote_node)
    g.add_node("finalize_reproduction", finalize_reproduction_node)
    g.add_node("finalize", finalize_node)
    g.add_node("meta_collect", meta_collect_node)
    g.add_node("meta_score", meta_score_node)
    g.add_node("meta_propose", meta_propose_node)
    g.add_node("meta_queue", meta_queue_node)

    g.set_entry_point("setup")
    g.add_edge("setup", "load_context")
    g.add_conditional_edges("load_context", route_after_load)
    g.add_edge("select_runner", "run_gate")
    g.add_conditional_edges("run_gate", route_after_run)
    g.add_edge("parse_validation_items", "validation_judge")
    g.add_edge("validation_judge", "apply_validation_plan")
    g.add_edge("apply_validation_plan", "run_pending_repro")
    g.add_conditional_edges("run_pending_repro", route_after_apply_validation)
    g.add_conditional_edges("diagnose_env", route_after_diagnose)
    g.add_edge("patch_bridge", "select_runner")
    g.add_conditional_edges("evaluate", route_after_eval)
    g.add_conditional_edges("parity_check", route_after_parity)
    g.add_edge("run_codegen", "parity_check")
    g.add_edge("promote", "finalize_reproduction")
    g.add_edge("finalize_reproduction", "finalize")
    g.add_edge("finalize", "meta_collect")
    g.add_edge("meta_collect", "meta_score")
    g.add_edge("meta_score", "meta_propose")
    g.add_edge("meta_propose", "meta_queue")
    g.add_edge("meta_queue", END)
    return g


def build_verify_group_graph():
    return _build_verify_group_state_graph().compile(checkpointer=MemorySaver())


def build_verify_group_graph_interruptible(checkpointer: MemorySaver | None = None):
    """Stepwise graph for LLM driver — interrupt after every node."""
    cp = checkpointer or MemorySaver()
    return _build_verify_group_state_graph().compile(
        checkpointer=cp,
        interrupt_after=list(_VERIFY_NODES),
    )


def run_verify_group(
    project_dir: Path,
    stage: str,
    group: str,
    *,
    project_id: str = "",
    thread_id: str = "default",
    orchestrator_run_id: str = "",
    group_context: dict[str, Any] | None = None,
    experiment_campaign: str = "",
    experiment_condition: str = "",
    experiment_hypothesis: str = "",
    max_steps: int = 80,
) -> dict[str, Any]:
    """Run verify_group with node gate enforcement between every step."""
    root = project_dir.parent.parent
    graph = build_verify_group_graph_interruptible()
    initial: VerifyGroupState = {
        "project_id": project_id or project_dir.name,
        "project_dir": str(project_dir.resolve()),
        "stage": stage,
        "group": group,
    }
    if orchestrator_run_id:
        initial["orchestrator_run_id"] = orchestrator_run_id
    if group_context:
        initial["group_context"] = group_context
    if experiment_campaign:
        initial["experiment_campaign"] = experiment_campaign
    if experiment_condition:
        initial["experiment_condition"] = experiment_condition
    if experiment_hypothesis:
        initial["experiment_hypothesis"] = experiment_hypothesis
    config = {"configurable": {"thread_id": thread_id}}

    graph.invoke(initial, config)
    last_completed = ""
    for _ in range(max_steps):
        snap = graph.get_state(config)
        next_nodes = list(snap.next) if snap.next else []
        if not next_nodes:
            break
        pending = next_nodes[0]
        state_values = dict(snap.values) if snap.values else {}
        run_dir = _run_dir_from_state(state_values) if state_values.get("run_id") else None

        if last_completed:
            prev_gate = validate_node_gate(
                root,
                "verify_group",
                last_completed,
                state=state_values,
                run_dir=run_dir,
            )
            if not prev_gate.ok:
                raise NodeGateBlocked(prev_gate)

        graph.invoke(None, config)
        snap_after = graph.get_state(config)
        state_after = dict(snap_after.values) if snap_after.values else {}
        run_dir_after = _run_dir_from_state(state_after) if state_after.get("run_id") else None

        gate = finalize_node_gate(
            root,
            "verify_group",
            pending,
            state=state_after,
            run_dir=run_dir_after,
        )
        if not gate.ok:
            raise NodeGateBlocked(gate)
        last_completed = pending

    final = graph.get_state(config)
    return dict(final.values) if final.values else {}