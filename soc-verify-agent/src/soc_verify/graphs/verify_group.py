"""LangGraph: main agent flow — instruct, observe, evaluate only."""

from __future__ import annotations

import json
import uuid
from datetime import date
from pathlib import Path
from typing import Any, Literal

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
from soc_verify.error_classify import bump_events, classify_exit_code, classify_stop_report
from soc_verify.loop_guard import build_signature, load_loop_guard, record_failure
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
from soc_verify.llm_runner import invoke_promote_decision, invoke_reproduction_finalize, invoke_sub_agent
from soc_verify.parity_eval import (
    LLM_REFERENCE_NAME,
    parity_allows_promote,
    run_parity_check,
    snapshot_llm_reference,
    write_parity_report,
)
from soc_verify.reproduction_scripts import (
    build_gate_reproduction_prompt,
    validate_gate_step,
    write_gate_reproduction_prompt,
)
from soc_verify.milestone_gate import check_milestone_gate
from soc_verify.models import load_yaml
from soc_verify.tag_cache import should_refresh_tag


def _project_dir(state: VerifyGroupState) -> Path:
    return Path(state["project_dir"])


def _run_dir(state: VerifyGroupState) -> Path:
    return _project_dir(state) / "runs" / state["run_id"]


def setup(state: VerifyGroupState) -> dict[str, Any]:
    run_id = state.get("run_id") or uuid.uuid4().hex[:12]
    as_of = state.get("as_of") or date.today().isoformat()
    run_dir = _project_dir(state) / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
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
            "fail_fast_stops": 0,
            "max_rounds": 20,
            "one_shot": False,
        },
        "gate_results": {},
        "questions": [],
    }


def load_context(state: VerifyGroupState) -> dict[str, Any]:
    project_dir = _project_dir(state)
    gaps = preflight_project(project_dir)
    if gaps:
        return {
            "info_gap": True,
            "info_gap_message": ", ".join(gaps),
            "verdict": "INFO_GAP",
        }
    stage = state.get("stage", "")
    if not stage or not is_valid_stage(stage):
        return {
            "info_gap": True,
            "info_gap_message": f"Invalid or missing stage: {stage!r}",
            "verdict": "INFO_GAP",
        }
    cache = load_yaml(project_dir / "cache.yaml")
    if should_refresh_tag(cache):
        return {
            "info_gap": True,
            "info_gap_message": "tag_watch due — orchestrator must refresh tag before verify",
            "verdict": "INFO_GAP",
        }

    group_dir = find_group_dir(project_dir, stage, state["group"])
    if not group_dir:
        return {
            "info_gap": True,
            "info_gap_message": f"Missing verification/{stage}/{state['group']}",
            "verdict": "INFO_GAP",
        }

    try:
        assert_preflight(project_dir, group_dir)
    except InfoGapError as e:
        return {
            "info_gap": True,
            "info_gap_message": str(e),
            "verdict": "INFO_GAP",
        }

    manifest = load_yaml(group_dir / "manifest.yaml")
    state_data = load_yaml(project_dir / "state.yaml")
    ok, msg = check_milestone_gate(manifest, state_data)
    if not ok:
        return {"info_gap": True, "info_gap_message": msg, "verdict": "INFO_GAP"}

    ctx = state.get("group_context") or load_group_context(group_dir)
    append_graph_trace(
        _run_dir(state),
        {"node": "load_context", "graph": "verify_group", "info_gap": False},
    )
    return {"info_gap": False, "group_context": ctx}


def select_runner_node(state: VerifyGroupState) -> dict[str, Any]:
    if state.get("info_gap"):
        return {}

    project_dir = _project_dir(state)
    stage = state["stage"]
    group = state["group"]
    script_path = resolve_group_script(project_dir, stage, group)
    script_name = script_path.name if script_path else f"{group}.py"

    loop = load_loop_guard(_run_dir(state))
    if loop.stalemate or state.get("force_mode") == "llm_full":
        return {"runner": "llm", "script_name": script_name, "force_mode": "llm_full"}

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
    return {
        "runner": runner,
        "runner_mode": runner_mode,
        "script_name": script_name,
        "round": state.get("round", 0) + 1,
    }


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
                events = bump_events(events, kind if kind in ("env", "tool", "info", "llm") else "llm")
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
                events = bump_events(events, kind if kind in ("env", "tool", "info", "llm") else "llm")
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
            partial = str(sub_stop.get("partial_verdict", "FAIL"))
            return {
                "sub_stop": sub_stop,
                "events": events,
                "verdict": partial,
                "error_kind": kind,
                "stalemate": loop.stalemate,
                "force_mode": loop.force_mode if loop.stalemate else "",
                "fix_round": state.get("fix_round", 0) + 1,
            }
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
        bump_kind = fail_kind if fail_kind in ("env", "tool", "info", "llm") else classify_exit_code(verdict.exit_code)
        events = bump_events(events, bump_kind)
        sig = build_signature(verdict=verdict)
        loop = record_failure(run_dir, sig)
        return {
            "gate_results": gate_results,
            "trust_score": score,
            "verdict": verdict.status,
            "events": events,
            "error_kind": fail_kind,
            "stalemate": loop.stalemate,
            "force_mode": loop.force_mode if loop.stalemate else "",
            "fix_round": state.get("fix_round", 0) + 1,
        }

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

    open_issues = 0 if state.get("verdict") == "PASS" else 1

    run_dir = _run_dir(state)
    events = dict(state.get("events", {}))
    metrics = CompletenessMetrics.from_events(events)
    write_run_metrics(run_dir, metrics.to_dict())

    root = _project_dir(state).parent.parent
    try:
        policies = load_policies(root)
    except Exception:
        policies = {}

    decision = evaluate_completeness_policy(
        metrics,
        policies,
        verdict=state.get("verdict", "FAIL"),
        trust_score=float(state.get("trust_score", 0.0)),
    )
    (run_dir / "completeness_decision.json").write_text(
        json.dumps(decision.to_dict(), indent=2),
        encoding="utf-8",
    )

    out: dict[str, Any] = {
        "open_issues": open_issues,
        "verdict": state.get("verdict", "FAIL"),
        "completeness": metrics.score,
        "jira_allowed": decision.jira_allowed,
        "continue_improvement": decision.continue_improvement,
    }
    if state.get("verdict") != "PASS":
        out["verdict"] = state.get("verdict", "FAIL")
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
    return {"runner": "llm", "runner_mode": "llm_diagnose_env"}


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
    return out


def promote_node(state: VerifyGroupState) -> dict[str, Any]:
    project_dir = _project_dir(state)
    run_dir = _run_dir(state)
    script_name = state.get("script_name", "")
    root = project_dir.parent.parent

    if script_name:
        script_path = resolve_group_script(project_dir, state["stage"], state["group"])
        if script_path and script_path.is_file():
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

    return {
        "completeness": metrics.score,
        "questions": questions,
        "jira_allowed": state.get("jira_allowed", False),
        "continue_improvement": state.get("continue_improvement", False),
    }


def route_after_load(state: VerifyGroupState) -> Literal["select_runner", "finalize"]:
    if state.get("info_gap"):
        return "finalize"
    return "select_runner"


def route_after_run(
    state: VerifyGroupState,
) -> Literal["select_runner", "evaluate", "diagnose_env", "finalize"]:
    if state.get("info_gap") or state.get("error_kind") == "info":
        return "finalize"
    if state.get("verdict") == "PASS":
        return "evaluate"
    if state.get("stalemate"):
        return "finalize"
    kind = str(state.get("error_kind", "verification"))
    if kind in ("env", "tool"):
        return "diagnose_env"
    return "select_runner"


def route_after_diagnose(state: VerifyGroupState) -> Literal["patch_bridge", "finalize"]:
    if state.get("error") in ("bridge_round_cap",):
        return "finalize"
    if state.get("stalemate"):
        return "finalize"
    return "patch_bridge"


def route_after_eval(
    state: VerifyGroupState,
) -> Literal["select_runner", "parity_check", "promote", "finalize"]:
    if state.get("info_gap"):
        return "finalize"
    if state.get("open_issues", 0) > 0:
        return "select_runner"
    if state.get("verdict") == "PASS" and state.get("continue_improvement"):
        return "select_runner"
    if state.get("verdict") == "PASS":
        return "parity_check"
    return "finalize"


def route_after_parity(state: VerifyGroupState) -> Literal["promote", "run_codegen", "finalize"]:
    if state.get("parity_ok"):
        return "promote"
    if state.get("error") == "codegen_round_cap":
        return "finalize"
    return "run_codegen"


_VERIFY_NODES = (
    "setup",
    "load_context",
    "select_runner",
    "run_gate",
    "diagnose_env",
    "patch_bridge",
    "evaluate",
    "parity_check",
    "run_codegen",
    "promote",
    "finalize_reproduction",
    "finalize",
)


def _build_verify_group_state_graph() -> StateGraph:
    g = StateGraph(VerifyGroupState)
    g.add_node("setup", setup)
    g.add_node("load_context", load_context)
    g.add_node("select_runner", select_runner_node)
    g.add_node("run_gate", run_gate)
    g.add_node("diagnose_env", diagnose_env_node)
    g.add_node("patch_bridge", patch_bridge_node)
    g.add_node("evaluate", evaluate_node)
    g.add_node("parity_check", parity_check_node)
    g.add_node("run_codegen", run_codegen_node)
    g.add_node("promote", promote_node)
    g.add_node("finalize_reproduction", finalize_reproduction_node)
    g.add_node("finalize", finalize_node)

    g.set_entry_point("setup")
    g.add_edge("setup", "load_context")
    g.add_conditional_edges("load_context", route_after_load)
    g.add_edge("select_runner", "run_gate")
    g.add_conditional_edges("run_gate", route_after_run)
    g.add_conditional_edges("diagnose_env", route_after_diagnose)
    g.add_edge("patch_bridge", "select_runner")
    g.add_conditional_edges("evaluate", route_after_eval)
    g.add_conditional_edges("parity_check", route_after_parity)
    g.add_edge("run_codegen", "parity_check")
    g.add_edge("promote", "finalize_reproduction")
    g.add_edge("finalize_reproduction", "finalize")
    g.add_edge("finalize", END)
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
) -> dict[str, Any]:
    graph = build_verify_group_graph()
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
    config = {"configurable": {"thread_id": thread_id}}
    return graph.invoke(initial, config=config)