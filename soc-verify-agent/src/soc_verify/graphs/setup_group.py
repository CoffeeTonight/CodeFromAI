"""LangGraph setup_group — milestone context, skill registry, LLM-adaptive bootstrap."""

from __future__ import annotations

import json
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from soc_verify.config import load_user_config
from soc_verify.graph_step import append_graph_trace
from soc_verify.graphs.setup_group_state import SetupGroupState
from soc_verify.models import load_yaml, save_yaml
from soc_verify.platform_telemetry import ensure_platform_baseline
from soc_verify.setup_adaptive import (
    build_milestone_context,
    build_setup_read_catalog,
    collect_skills_summary,
    load_user_skillset,
    validate_bootstrap,
    validate_setup_adapt,
    write_bootstrap_prompt,
    write_milestone_context_artifact,
    write_read_catalog_artifact,
    write_setup_adapt_prompt,
)
from soc_verify.setup_wizard import load_setup_state, save_setup_state
from soc_verify.skill_registry import register_skillset_from_text
from soc_verify.skill_materialize import (
    bootstrap_group_ops,
    ensure_verify_handoff,
    materialize_from_registry,
    primary_materialized_group,
)
from soc_verify.graphs.verify_group import run_verify_group


_SETUP_NODES = [
    "setup",
    "milestone_context",
    "register_skills",
    "materialize_verification",
    "llm_adapt",
    "llm_bootstrap_scripts",
    "bootstrap_group_ops",
    "verify_smoke",
    "finalize",
]


def _root(state: SetupGroupState) -> Path:
    return Path(state["root"])


def _project_dir(state: SetupGroupState) -> Path:
    return Path(state["project_dir"])


def _run_dir(state: SetupGroupState) -> Path:
    return _project_dir(state) / "runs" / "setup" / state["run_id"]


def setup(state: SetupGroupState) -> dict[str, Any]:
    root = _root(state)
    project_dir = _project_dir(state)
    run_id = state.get("run_id") or uuid.uuid4().hex[:12]
    as_of = state.get("as_of") or date.today().isoformat()
    run_dir = project_dir / "runs" / "setup" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "skills").mkdir(parents=True, exist_ok=True)
    (project_dir / "scripts").mkdir(parents=True, exist_ok=True)
    (project_dir / "tools").mkdir(parents=True, exist_ok=True)
    ensure_platform_baseline(root, trigger="setup_group_setup")
    append_graph_trace(run_dir, {"node": "setup", "graph": "setup_group"})
    return {
        "run_id": run_id,
        "as_of": as_of,
        "events": {"setup": "ok"},
    }


def milestone_context(state: SetupGroupState) -> dict[str, Any]:
    root = _root(state)
    project_dir = _project_dir(state)
    run_dir = _run_dir(state)
    try:
        config = load_user_config(root)
        cfg_raw = config.raw
    except FileNotFoundError:
        cfg_raw = None

    ctx = build_milestone_context(root, project_dir, config=cfg_raw)
    write_milestone_context_artifact(run_dir, ctx)
    append_graph_trace(run_dir, {"node": "milestone_context", "graph": "setup_group"})

    proj_state = load_yaml(project_dir / "state.yaml") or {}
    return {
        "milestone_context": ctx,
        "milestone_plan": ctx.get("schedule_plan", ""),
        "current_milestone": ctx.get("current_milestone") or str(proj_state.get("current_milestone", "")),
        "events": {"milestone_context": "ok"},
    }


def register_skills(state: SetupGroupState) -> dict[str, Any]:
    root = _root(state)
    project_dir = _project_dir(state)
    run_dir = _run_dir(state)

    text = state.get("user_skillset") or load_user_skillset(root, project_dir, state_override=state)
    current = state.get("current_milestone", "")
    registered = register_skillset_from_text(
        project_dir,
        text,
        default_milestone=current,
        source="setup_group",
    )

    summary = {
        "count": len(registered),
        "skill_ids": [r["id"] for r in registered],
        "had_intake": bool(text.strip()),
    }
    (run_dir / "skills_registered.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    append_graph_trace(run_dir, {"node": "register_skills", "graph": "setup_group"})
    return {
        "skills_registered": len(registered),
        "skill_ids": summary["skill_ids"],
        "events": {"register_skills": summary},
    }


def materialize_verification(state: SetupGroupState) -> dict[str, Any]:
    """SKILL.md frontmatter → verification MD + manifest."""
    project_dir = _project_dir(state)
    run_dir = _run_dir(state)
    milestone = str(state.get("current_milestone") or "")
    materialized = materialize_from_registry(
        project_dir,
        default_milestone=milestone,
        milestone_filter=milestone,
        overwrite=False,
    )
    (run_dir / "materialize_verification.json").write_text(
        json.dumps(materialized, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    append_graph_trace(
        run_dir,
        {
            "node": "materialize_verification",
            "graph": "setup_group",
            "count": sum(1 for m in materialized if m.get("materialized")),
        },
    )
    groups = [m for m in materialized if m.get("materialized")]
    return {
        "materialized_groups": groups,
        "events": {"materialize_verification": {"groups": len(groups)}},
    }


def llm_adapt(state: SetupGroupState) -> dict[str, Any]:
    """Platform boundary — prompt artifact; LLM writes setup_adapt.json via sandbox."""
    project_dir = _project_dir(state)
    run_dir = _run_dir(state)
    ctx = state.get("milestone_context") or json.loads(
        (run_dir / "milestone_context.json").read_text(encoding="utf-8")
    )
    milestone = str(ctx.get("current_milestone") or state.get("current_milestone") or "")
    skills, registry = collect_skills_summary(project_dir, milestone=milestone)
    materialized = state.get("materialized_groups") or []
    if not materialized and (run_dir / "materialize_verification.json").is_file():
        materialized = [
            g
            for g in json.loads((run_dir / "materialize_verification.json").read_text(encoding="utf-8"))
            if g.get("materialized")
        ]
    catalog = build_setup_read_catalog(
        project_dir,
        milestone=milestone,
        run_dir=run_dir,
        materialized_groups=materialized,
    )
    write_read_catalog_artifact(run_dir, catalog)
    write_setup_adapt_prompt(
        run_dir,
        context=ctx,
        skills=skills,
        registry=registry,
        read_catalog=catalog,
    )

    adapt_path = run_dir / "setup_adapt.json"
    adapt: dict[str, Any] = {}
    if adapt_path.is_file():
        adapt = json.loads(adapt_path.read_text(encoding="utf-8"))

    append_graph_trace(run_dir, {"node": "llm_adapt", "graph": "setup_group"})
    return {
        "setup_adapt": adapt,
        "events": {"llm_adapt": "prompt_ready"},
    }


def llm_bootstrap_scripts(state: SetupGroupState) -> dict[str, Any]:
    project_dir = _project_dir(state)
    run_dir = _run_dir(state)
    ctx = state.get("milestone_context") or {}
    adapt = state.get("setup_adapt") or {}
    if not adapt and (run_dir / "setup_adapt.json").is_file():
        adapt = json.loads((run_dir / "setup_adapt.json").read_text(encoding="utf-8"))
    milestone = str(ctx.get("current_milestone") or state.get("current_milestone") or "")
    skills, _ = collect_skills_summary(project_dir, milestone=milestone)
    catalog: dict[str, Any] = {}
    if (run_dir / "read_catalog.json").is_file():
        catalog = json.loads((run_dir / "read_catalog.json").read_text(encoding="utf-8"))
    else:
        materialized = state.get("materialized_groups") or []
        catalog = build_setup_read_catalog(
            project_dir,
            milestone=milestone,
            run_dir=run_dir,
            materialized_groups=materialized,
        )
        write_read_catalog_artifact(run_dir, catalog)
    write_bootstrap_prompt(run_dir, context=ctx, adapt=adapt, skills=skills, read_catalog=catalog)

    check = validate_bootstrap(project_dir, run_dir)
    append_graph_trace(run_dir, {"node": "llm_bootstrap_scripts", "graph": "setup_group", "ok": check["ok"]})
    return {
        "bootstrap_ok": check["ok"],
        "events": {"llm_bootstrap_scripts": check},
    }


def bootstrap_group_ops_node(state: SetupGroupState) -> dict[str, Any]:
    project_dir = _project_dir(state)
    run_dir = _run_dir(state)
    groups = state.get("materialized_groups") or []
    if not groups and (run_dir / "materialize_verification.json").is_file():
        groups = [
            g
            for g in json.loads((run_dir / "materialize_verification.json").read_text(encoding="utf-8"))
            if g.get("materialized")
        ]
    bootstrapped: list[dict[str, Any]] = []
    for g in groups:
        bootstrapped.append(
            bootstrap_group_ops(project_dir, stage=str(g["stage"]), group=str(g["group"]))
        )
    append_graph_trace(run_dir, {"node": "bootstrap_group_ops", "graph": "setup_group"})
    return {"ops_bootstrapped": bootstrapped, "events": {"bootstrap_group_ops": bootstrapped}}


def verify_smoke(state: SetupGroupState) -> dict[str, Any]:
    """One unattended verify_group lap for primary materialized group."""
    root = _root(state)
    project_dir = _project_dir(state)
    run_dir = _run_dir(state)
    groups = state.get("materialized_groups") or []
    primary = primary_materialized_group(groups)
    if not primary:
        append_graph_trace(run_dir, {"node": "verify_smoke", "skipped": True})
        return {
            "verify_smoke_verdict": "SKIPPED",
            "verify_smoke_result": {"reason": "no_materialized_group"},
            "events": {"verify_smoke": "skipped"},
        }

    stage = str(primary["stage"])
    group = str(primary["group"])
    ensure_verify_handoff(project_dir, stage=stage, group=group, run_dir=run_dir)
    thread_id = f"setup-smoke-{state.get('run_id', 'x')}"
    try:
        result = run_verify_group(
            project_dir,
            stage,
            group,
            project_id=state.get("project_id", project_dir.name),
            thread_id=thread_id,
        )
        verdict = str(result.get("verdict") or "FAIL")
    except Exception as exc:
        result = {"error": str(exc)}
        verdict = "ERROR"

    (run_dir / "verify_smoke_result.json").write_text(
        json.dumps({"verdict": verdict, "result": result}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    append_graph_trace(
        run_dir,
        {"node": "verify_smoke", "graph": "setup_group", "stage": stage, "group": group, "verdict": verdict},
    )
    return {
        "verify_smoke_verdict": verdict,
        "verify_smoke_result": result,
        "events": {"verify_smoke": verdict},
    }


def finalize(state: SetupGroupState) -> dict[str, Any]:
    root = _root(state)
    project_dir = _project_dir(state)
    run_dir = _run_dir(state)

    workflow = {
        "graph": "setup_group",
        "project_id": state.get("project_id", project_dir.name),
        "run_id": state.get("run_id", ""),
        "milestone_plan": state.get("milestone_plan", ""),
        "current_milestone": state.get("current_milestone", ""),
        "skills_registered": state.get("skills_registered", 0),
        "skill_ids": state.get("skill_ids") or [],
        "bootstrap_ok": state.get("bootstrap_ok", False),
        "materialized_groups": state.get("materialized_groups") or [],
        "verify_smoke_verdict": state.get("verify_smoke_verdict", ""),
        "artifacts": {
            "milestone_context": str(run_dir / "milestone_context.json"),
            "skills_registered": str(run_dir / "skills_registered.json"),
            "setup_adapt": str(run_dir / "setup_adapt.json"),
            "run_beginner": str(project_dir / "scripts" / "run_beginner.sh"),
            "materialize": str(run_dir / "materialize_verification.json"),
            "read_catalog": str(run_dir / "read_catalog.json"),
            "verify_smoke": str(run_dir / "verify_smoke_result.json"),
        },
    }
    (run_dir / "setup_workflow.json").write_text(
        json.dumps(workflow, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    setup_state = load_setup_state(root)
    completed = list(setup_state.get("completed_steps") or [])
    if "setup_group" not in completed:
        completed.append("setup_group")
    setup_state["completed_steps"] = completed
    setup_state.setdefault("answers", {})["setup_group_run_id"] = state.get("run_id", "")
    save_setup_state(root, setup_state)

    meta_path = project_dir / "meta" / "setup_status.yaml"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    save_yaml(
        meta_path,
        {
            "setup_group_complete": True,
            "last_run_id": state.get("run_id", ""),
            "skills_count": state.get("skills_registered", 0),
            "bootstrap_ok": state.get("bootstrap_ok", False),
        },
    )

    append_graph_trace(run_dir, {"node": "finalize", "graph": "setup_group", "verdict": "PASS"})
    return {"verdict": "PASS", "events": {"finalize": workflow}}


def _build_setup_group_state_graph() -> StateGraph:
    g: StateGraph = StateGraph(SetupGroupState)
    g.add_node("setup", setup)
    g.add_node("milestone_context", milestone_context)
    g.add_node("register_skills", register_skills)
    g.add_node("materialize_verification", materialize_verification)
    g.add_node("llm_adapt", llm_adapt)
    g.add_node("llm_bootstrap_scripts", llm_bootstrap_scripts)
    g.add_node("bootstrap_group_ops", bootstrap_group_ops_node)
    g.add_node("verify_smoke", verify_smoke)
    g.add_node("finalize", finalize)

    g.set_entry_point("setup")
    g.add_edge("setup", "milestone_context")
    g.add_edge("milestone_context", "register_skills")
    g.add_edge("register_skills", "materialize_verification")
    g.add_edge("materialize_verification", "llm_adapt")
    g.add_edge("llm_adapt", "llm_bootstrap_scripts")
    g.add_edge("llm_bootstrap_scripts", "bootstrap_group_ops")
    g.add_edge("bootstrap_group_ops", "verify_smoke")
    g.add_edge("verify_smoke", "finalize")
    g.add_edge("finalize", END)
    return g


def build_setup_group_graph():
    return _build_setup_group_state_graph().compile(checkpointer=MemorySaver())


def build_setup_group_graph_interruptible(checkpointer: MemorySaver | None = None):
    cp = checkpointer or MemorySaver()
    return _build_setup_group_state_graph().compile(
        checkpointer=cp,
        interrupt_after=list(_SETUP_NODES),
    )


def run_setup_group(
    root: Path,
    project_id: str,
    *,
    user_skillset: str = "",
    thread_id: str = "default",
) -> dict[str, Any]:
    graph = build_setup_group_graph()
    project_dir = root / "projects" / project_id
    initial: SetupGroupState = {
        "root": str(root.resolve()),
        "project_id": project_id,
        "project_dir": str(project_dir.resolve()),
    }
    if user_skillset:
        initial["user_skillset"] = user_skillset
    config = {"configurable": {"thread_id": thread_id}}
    return graph.invoke(initial, config=config)