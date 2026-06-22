"""Top-level LangGraph orchestrator — all agent work flows through here."""

from __future__ import annotations

import json
import uuid
from datetime import date
from pathlib import Path
from typing import Any, Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from soc_verify.acquisition import project_acquisition_status, workspace_acquisition_status
from soc_verify.config import load_user_config
from soc_verify.graphs.orchestrator_state import OrchestratorState, WorkItem
from soc_verify.graphs.verify_group import run_verify_group
from soc_verify.group_context import load_group_context
from soc_verify.intake_ops import (
    refresh_project_intake,
    refresh_project_search,
    refresh_state_sync,
)
from soc_verify.knowledge_ops import refresh_knowledge_collect
from soc_verify.milestone_gate import check_milestone_gate
from soc_verify.models import load_yaml
from soc_verify.runner import load_active_projects
from soc_verify.stages import find_group_dir, is_valid_stage
from soc_verify.tag_watch import refresh_if_due
from soc_verify.reproduction_scripts import (
    build_sequence_reproduction_prompt,
    validate_orchestrator,
    write_sequence_reproduction_prompt,
)
from soc_verify.validation_autonomy import filter_work_queue_by_validation
from soc_verify.graph_step import append_graph_trace
from soc_verify.branch_scorecard import (
    append_project_scorecard_history,
    build_all_branch_scorecards,
    write_branch_scorecard,
)
from soc_verify.platform_telemetry import ensure_platform_baseline, record_platform_use
from soc_verify.repro_bundle import build_repro_bundle, build_repro_manifest


def _root(state: OrchestratorState) -> Path:
    return Path(state["root"])


def _orch_run_dir(state: OrchestratorState) -> Path:
    d = _root(state) / "runs" / "orchestrator" / state["run_id"]
    d.mkdir(parents=True, exist_ok=True)
    return d


def _acq_priority(acq: str) -> int:
    return {
        "project_search": 0,
        "project_intake": 1,
        "knowledge_collect": 2,
        "state_sync": 3,
        "tag_watch": 4,
    }.get(acq, 9)


def _build_work_queue(
    root: Path,
    *,
    mode: str,
    project_id: str = "",
    stage: str = "",
    group: str = "",
) -> list[WorkItem]:
    config = load_user_config(root)
    today = date.today()
    ws = workspace_acquisition_status(root, config, today)
    queue: list[WorkItem] = []

    if mode == "single_verify":
        if not (project_id and stage and group):
            return []
        return [{"kind": "verify", "project_id": project_id, "stage": stage, "group": group}]

    if ws["project_search"].get("due"):
        queue.append({"kind": "acquisition", "acq": "project_search"})

    registry = root / "registry"
    active_ids = load_active_projects(registry, today.isoformat())
    projects_root = config.projects_root

    for pid in active_ids:
        project_dir = projects_root / pid
        if not project_dir.is_dir():
            continue
        for st in project_acquisition_status(project_dir, config, today):
            if st.due:
                queue.append({"kind": "acquisition", "acq": st.kind, "project_id": pid})

        state_data = load_yaml(project_dir / "state.yaml")
        for item in state_data.get("verification_groups_due") or []:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status", ""))
            if status in ("pending", "scheduled"):
                queue.append(
                    {
                        "kind": "verify",
                        "project_id": pid,
                        "stage": str(item.get("stage", "")),
                        "group": str(item.get("group", "")),
                    }
                )

    def sort_key(w: WorkItem) -> tuple:
        if w.get("kind") == "acquisition":
            return (_acq_priority(str(w.get("acq", ""))), w.get("project_id", ""), 0, "")
        return (4, w.get("project_id", ""), 0, w.get("group", ""))

    queue.sort(key=sort_key)
    return filter_work_queue_by_validation(root, queue)


def setup(state: OrchestratorState) -> dict[str, Any]:
    run_id = state.get("run_id") or uuid.uuid4().hex[:12]
    as_of = state.get("as_of") or date.today().isoformat()
    ensure_platform_baseline(_root(state), trigger="orchestrator_setup")
    append_graph_trace(_orch_run_dir({**state, "run_id": run_id, "as_of": as_of}), {"node": "setup", "graph": "orchestrator"})
    return {
        "run_id": run_id,
        "as_of": as_of,
        "work_index": 0,
        "acquisition_log": [],
        "verify_results": [],
        "info_gap": False,
    }


def plan_work(state: OrchestratorState) -> dict[str, Any]:
    root = _root(state)
    mode = state.get("mode", "workspace")
    queue = _build_work_queue(
        root,
        mode=mode,
        project_id=state.get("project_id", ""),
        stage=state.get("stage", ""),
        group=state.get("group", ""),
    )
    out: dict[str, Any] = {"work_queue": queue, "work_index": 0}
    if queue:
        out["current_work"] = queue[0]
    else:
        out["verdict"] = "PASS"
        out["error"] = "no_work"
    append_graph_trace(_orch_run_dir(state), {"node": "plan_work", "queue_len": len(queue)})
    return out


def run_acquisition(state: OrchestratorState) -> dict[str, Any]:
    work = state.get("current_work") or {}
    if work.get("kind") != "acquisition":
        return {}

    root = _root(state)
    config = load_user_config(root)
    acq = str(work.get("acq", ""))
    pid = work.get("project_id", "")
    log_entry: dict[str, Any] = {"acq": acq, "project_id": pid, "status": "ok"}

    try:
        if acq == "project_search":
            result = refresh_project_search(root, config)
            log_entry["result"] = result
        elif acq == "project_intake" and pid:
            result = refresh_project_intake(root / "projects" / pid, config)
            log_entry["result"] = result
        elif acq == "knowledge_collect" and pid:
            project_dir = root / "projects" / pid
            result = refresh_knowledge_collect(
                root,
                project_dir,
                config,
                normalize=config.knowledge_auto_normalize,
            )
            log_entry["result"] = result
            (_orch_run_dir(state) / f"knowledge_collect_{pid}.json").write_text(
                json.dumps(log_entry, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        elif acq == "state_sync" and pid:
            result = refresh_state_sync(root / "projects" / pid, config)
            log_entry["result"] = result
        elif acq == "tag_watch" and pid:
            project_dir = root / "projects" / pid
            cache = load_yaml(project_dir / "cache.yaml")
            cache, tag_meta = refresh_if_due(project_dir, config, cache=cache)
            if tag_meta.get("refreshed"):
                log_entry["status"] = "refreshed"
                log_entry["tag_meta"] = tag_meta
                log_entry["message"] = (
                    f"tag_watch — mode={tag_meta.get('mode')} "
                    f"tag_changed={tag_meta.get('tag_changed', False)}"
                )
            else:
                log_entry["status"] = "fresh"
            (_orch_run_dir(state) / f"tag_watch_{pid}.json").write_text(
                json.dumps(log_entry, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        else:
            log_entry["status"] = "skipped"
    except Exception as e:
        log_entry["status"] = "error"
        log_entry["error"] = str(e)

    append_graph_trace(_orch_run_dir(state), {"node": "run_acquisition", "acq": acq, "status": log_entry.get("status")})
    return {"acquisition_log": [log_entry]}


def prepare_verify(state: OrchestratorState) -> dict[str, Any]:
    work = state.get("current_work") or {}
    if work.get("kind") != "verify":
        return {}

    root = _root(state)
    pid = str(work.get("project_id", ""))
    stage = str(work.get("stage", ""))
    group = str(work.get("group", ""))

    if not is_valid_stage(stage):
        return {
            "info_gap": True,
            "info_gap_message": f"Invalid stage: {stage}",
            "verdict": "INFO_GAP",
        }

    project_dir = root / "projects" / pid
    group_dir = find_group_dir(project_dir, stage, group)
    if group_dir is None:
        return {
            "info_gap": True,
            "info_gap_message": f"Missing verification/{stage}/{group}",
            "verdict": "INFO_GAP",
        }

    cache = load_yaml(project_dir / "cache.yaml")
    try:
        config = load_user_config(root)
        cache, _tag_meta = refresh_if_due(project_dir, config, cache=cache)
    except FileNotFoundError:
        pass

    manifest = load_yaml(group_dir / "manifest.yaml")
    state_data = load_yaml(project_dir / "state.yaml")
    due_item = next(
        (
            x
            for x in (state_data.get("verification_groups_due") or [])
            if isinstance(x, dict) and x.get("stage") == stage and x.get("group") == group
        ),
        {},
    )
    root = project_dir.parent.parent
    ok, msg = check_milestone_gate(
        manifest,
        state_data,
        group_status=str(due_item.get("status", "")),
        root=root,
    )
    if not ok:
        return {"info_gap": True, "info_gap_message": msg, "verdict": "INFO_GAP"}

    ctx = load_group_context(group_dir)
    append_graph_trace(_orch_run_dir(state), {"node": "prepare_verify", "project_id": pid, "stage": stage, "group": group})
    return {
        "project_id": pid,
        "stage": stage,
        "group": group,
        "group_context": ctx,
        "info_gap": False,
    }


def dispatch_verify(state: OrchestratorState) -> dict[str, Any]:
    if state.get("info_gap"):
        return {
            "verify_results": [
                {
                    "project_id": state.get("project_id"),
                    "stage": state.get("stage"),
                    "group": state.get("group"),
                    "verdict": "INFO_GAP",
                    "message": state.get("info_gap_message"),
                }
            ],
            "verdict": "INFO_GAP",
        }

    root = _root(state)
    pid = state["project_id"]
    project_dir = root / "projects" / pid
    thread_id = f"orch-{state['run_id']}-{pid}-{state['stage']}-{state['group']}"

    result = run_verify_group(
        project_dir,
        state["stage"],
        state["group"],
        project_id=pid,
        thread_id=thread_id,
        orchestrator_run_id=state["run_id"],
        group_context=state.get("group_context"),
        experiment_campaign=state.get("experiment_campaign", ""),
        experiment_condition=state.get("experiment_condition", ""),
        experiment_hypothesis=state.get("experiment_hypothesis", ""),
    )

    entry = {
        "project_id": pid,
        "stage": state["stage"],
        "group": state["group"],
        "verdict": result.get("verdict"),
        "completeness": result.get("completeness"),
        "run_id": result.get("run_id"),
    }
    append_graph_trace(
        _orch_run_dir(state),
        {"node": "dispatch_verify", "verdict": entry.get("verdict"), "run_id": entry.get("run_id")},
    )
    return {
        "verify_results": [entry],
        "verdict": result.get("verdict", "FAIL"),
    }


def advance_work(state: OrchestratorState) -> dict[str, Any]:
    idx = int(state.get("work_index", 0)) + 1
    queue = state.get("work_queue") or []
    out: dict[str, Any] = {"work_index": idx}
    if idx < len(queue):
        out["current_work"] = queue[idx]
        out["info_gap"] = False
        out["info_gap_message"] = ""
    return out


def finalize_reproduction_sequence(state: OrchestratorState) -> dict[str, Any]:
    """After all work items: ensure project orchestrator + full sequence scripts exist."""
    root = _root(state)
    run_dir = _orch_run_dir(state)
    verify_results = list(state.get("verify_results") or [])
    if not verify_results:
        return {}

    by_project: dict[str, list[dict[str, Any]]] = {}
    for entry in verify_results:
        if not isinstance(entry, dict):
            continue
        pid = str(entry.get("project_id", ""))
        if pid and entry.get("verdict") == "PASS":
            by_project.setdefault(pid, []).append(entry)

    validations: list[dict[str, Any]] = []
    for pid, results in by_project.items():
        project_dir = root / "projects" / pid
        if not project_dir.is_dir():
            continue
        payload = build_sequence_reproduction_prompt(
            project_dir=project_dir,
            verify_results=results,
        )
        write_sequence_reproduction_prompt(run_dir, payload)
        validation = validate_orchestrator(project_dir)
        validations.append({"project_id": pid, **validation})

        tpl = root / "templates" / "reproduction_finalize_sequence.md"
        if tpl.is_file():
            text = tpl.read_text(encoding="utf-8").replace("{{project_id}}", pid)
            text = text.replace("{{run_id}}", state["run_id"])
            (run_dir / f"reproduction_sequence_{pid}.md").write_text(text, encoding="utf-8")

    return {"reproduction_sequence_validations": validations}


def finalize(state: OrchestratorState) -> dict[str, Any]:
    root = _root(state)
    run_dir = _orch_run_dir(state)
    from soc_verify.experiment import register_campaign_run, resolve_experiment_tags, write_experiment_run

    tags = resolve_experiment_tags(
        root,
        campaign=state.get("experiment_campaign", ""),
        condition=state.get("experiment_condition", ""),
        hypothesis=state.get("experiment_hypothesis", ""),
    )
    write_experiment_run(run_dir, tags)
    register_campaign_run(
        root,
        tags,
        run_meta={
            "run_id": state["run_id"],
            "graph_id": "orchestrator",
            "verdict": state.get("verdict", "PASS"),
        },
    )

    append_graph_trace(run_dir, {"node": "finalize", "graph": "orchestrator"})
    summary = {
        "run_id": state["run_id"],
        "as_of": state.get("as_of"),
        "mode": state.get("mode"),
        "work_queue_len": len(state.get("work_queue") or []),
        "acquisition_log": state.get("acquisition_log") or [],
        "verify_results": state.get("verify_results") or [],
        "verdict": state.get("verdict", "PASS"),
    }
    (run_dir / "workflow.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    state_dict: dict[str, Any] = {
        "run_id": state["run_id"],
        "project_id": state.get("project_id", ""),
        "stage": state.get("stage", ""),
        "group": state.get("group", ""),
        "verdict": state.get("verdict", "PASS"),
        "trust_score": 0.0,
        "completeness": 0.0,
        "events": {},
        "as_of": state.get("as_of"),
        "questions": [],
    }
    vr = state.get("verify_results") or []
    if vr:
        last = vr[-1]
        state_dict["trust_score"] = float(last.get("trust_score") or 0.0)
        state_dict["completeness"] = float(last.get("completeness") or 0.0)
        state_dict["verdict"] = last.get("verdict", state_dict["verdict"])

    scorecard = build_all_branch_scorecards(
        root,
        root / "projects" / (state.get("project_id") or "_orchestrator"),
        run_dir,
        state_dict,
        graph_id="orchestrator",
    )
    write_branch_scorecard(run_dir, scorecard)
    orch_project = root / "projects" / ".platform"
    orch_project.mkdir(parents=True, exist_ok=True)
    append_project_scorecard_history(orch_project, scorecard)

    branches = scorecard.get("branches") or []
    mean_success = sum(float(b.get("success_rate", 0)) for b in branches) / max(1, len(branches))

    record_platform_use(
        root,
        kind="orchestrator_complete",
        graph_id="orchestrator",
        run_id=state["run_id"],
        verdict=str(state.get("verdict", "PASS")),
        success_rate=mean_success,
        project_id=state.get("project_id", ""),
        extra={"verify_results_count": len(vr)},
    )

    manifest = build_repro_manifest(
        root,
        run_dir=run_dir,
        project_dir=None,
        purpose=f"orchestrator mode={state.get('mode')} verdict={state.get('verdict')}",
        graph_id="orchestrator",
        run_id=state["run_id"],
        state=state_dict,
    )
    build_repro_bundle(root, run_dir, manifest)

    return summary


def route_first_work(
    state: OrchestratorState,
) -> Literal["run_acquisition", "prepare_verify", "finalize_reproduction_sequence"]:
    queue = state.get("work_queue") or []
    if not queue:
        return "finalize_reproduction_sequence"
    work = queue[0]
    if work.get("kind") == "acquisition":
        return "run_acquisition"
    return "prepare_verify"


def route_after_advance(
    state: OrchestratorState,
) -> Literal["run_acquisition", "prepare_verify", "finalize_reproduction_sequence"]:
    return route_after_advance_to_end(state)


def route_after_prepare(state: OrchestratorState) -> Literal["dispatch_verify", "advance_work"]:
    if state.get("info_gap"):
        return "advance_work"
    return "dispatch_verify"


def route_after_verify(state: OrchestratorState) -> Literal["advance_work", "finalize_reproduction_sequence"]:
    idx = int(state.get("work_index", 0))
    queue = state.get("work_queue") or []
    if idx + 1 >= len(queue):
        return "finalize_reproduction_sequence"
    return "advance_work"


def route_after_advance_to_end(
    state: OrchestratorState,
) -> Literal["run_acquisition", "prepare_verify", "finalize_reproduction_sequence"]:
    queue = state.get("work_queue") or []
    idx = int(state.get("work_index", 0))
    if idx >= len(queue):
        return "finalize_reproduction_sequence"
    work = queue[idx]
    if work.get("kind") == "acquisition":
        return "run_acquisition"
    return "prepare_verify"


def _build_orchestrator_state_graph() -> StateGraph:
    g = StateGraph(OrchestratorState)
    g.add_node("setup", setup)
    g.add_node("plan_work", plan_work)
    g.add_node("run_acquisition", run_acquisition)
    g.add_node("prepare_verify", prepare_verify)
    g.add_node("dispatch_verify", dispatch_verify)
    g.add_node("advance_work", advance_work)
    g.add_node("finalize_reproduction_sequence", finalize_reproduction_sequence)
    g.add_node("finalize", finalize)

    g.set_entry_point("setup")
    g.add_edge("setup", "plan_work")
    g.add_conditional_edges("plan_work", route_first_work)
    g.add_edge("run_acquisition", "advance_work")
    g.add_conditional_edges("advance_work", route_after_advance)
    g.add_conditional_edges("prepare_verify", route_after_prepare)
    g.add_conditional_edges("dispatch_verify", route_after_verify)
    g.add_edge("finalize_reproduction_sequence", "finalize")
    g.add_edge("finalize", END)

    return g


def build_orchestrator_graph():
    return _build_orchestrator_state_graph().compile(checkpointer=MemorySaver())


def build_orchestrator_graph_interruptible(checkpointer: MemorySaver | None = None):
    cp = checkpointer or MemorySaver()
    return _build_orchestrator_state_graph().compile(
        checkpointer=cp,
        interrupt_after=[
            "setup",
            "plan_work",
            "run_acquisition",
            "prepare_verify",
            "dispatch_verify",
            "advance_work",
            "finalize_reproduction_sequence",
            "finalize",
        ],
    )


def run_orchestrator(
    root: Path,
    *,
    mode: Literal["workspace", "single_verify"] = "workspace",
    project_id: str = "",
    stage: str = "",
    group: str = "",
    thread_id: str = "orchestrator",
    experiment_campaign: str = "",
    experiment_condition: str = "",
    experiment_hypothesis: str = "",
) -> dict[str, Any]:
    graph = build_orchestrator_graph()
    initial: OrchestratorState = {
        "root": str(root.resolve()),
        "mode": mode,
        "project_id": project_id,
        "stage": stage,
        "group": group,
    }
    if experiment_campaign:
        initial["experiment_campaign"] = experiment_campaign
    if experiment_condition:
        initial["experiment_condition"] = experiment_condition
    if experiment_hypothesis:
        initial["experiment_hypothesis"] = experiment_hypothesis
    return graph.invoke(initial, config={"configurable": {"thread_id": thread_id}})