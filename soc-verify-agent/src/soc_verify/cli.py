"""CLI entrypoints."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from soc_verify.acquisition import project_acquisition_status, workspace_acquisition_status
from soc_verify.graph_http import serve_graph_api
from soc_verify.graph_session import (
    run_until_done,
    session_invoke_llm,
    session_resume,
    session_sandbox,
    session_status,
    session_tick,
    start_session,
)
from soc_verify.graph_spec import load_flow_spec
from soc_verify.feedback_rubric import write_user_feedback
from soc_verify.graphs.orchestrator import run_orchestrator
from soc_verify.platform_telemetry import ensure_platform_baseline, load_cumulative_stats
from soc_verify.models import save_yaml
from soc_verify.runner import load_active_projects
from soc_verify.stages import VALID_STAGES, is_valid_stage, list_groups_in_stage, load_stages_registry
from soc_verify.tag_cache import apply_tag_replace, should_refresh_tag
from soc_verify.models import load_yaml
from soc_verify.trust_eval import evaluate_script, write_trust_report


def _print_orchestrator_result(result: dict) -> None:
    slim = {k: v for k, v in result.items() if k not in ("acquisition_log", "verify_results")}
    if result.get("verify_results"):
        slim["verify_results"] = result["verify_results"]
    if result.get("acquisition_log"):
        slim["acquisition_log"] = result["acquisition_log"]
    print(json.dumps(slim, indent=2, default=str, ensure_ascii=False))


def cmd_run(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    ensure_platform_baseline(root, trigger="cli_run")
    result = run_orchestrator(root, mode="workspace", thread_id=args.thread)
    _print_orchestrator_result(result)
    verdict = result.get("verdict", "FAIL")
    return 0 if verdict == "PASS" else 1


def cmd_verify(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    ensure_platform_baseline(root, trigger="cli_verify")
    if not is_valid_stage(args.stage):
        print(json.dumps({"error": f"Invalid stage: {args.stage}", "valid": list(VALID_STAGES)}, indent=2))
        return 2
    result = run_orchestrator(
        root,
        mode="single_verify",
        project_id=args.project,
        stage=args.stage,
        group=args.group,
        thread_id=args.thread,
        experiment_campaign=getattr(args, "campaign", "") or "",
        experiment_condition=getattr(args, "condition", "") or "",
        experiment_hypothesis=getattr(args, "hypothesis", "") or "",
    )
    _print_orchestrator_result(result)
    vr = result.get("verify_results") or []
    verdict = vr[-1].get("verdict") if vr else result.get("verdict", "FAIL")
    return 0 if verdict == "PASS" else 1


def cmd_tag_replace(args: argparse.Namespace) -> int:
    project_dir = Path(args.root).resolve() / "projects" / args.project
    cache = apply_tag_replace(project_dir, args.tag, clone_path=args.clone)
    print(json.dumps(cache.get("tag"), indent=2))
    return 0


def cmd_trust_eval(args: argparse.Namespace) -> int:
    project_dir = Path(args.root).resolve() / "projects" / args.project
    script = project_dir / args.script
    run_dir = project_dir / "runs" / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    result = evaluate_script(project_dir, script)
    write_trust_report(run_dir, result)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.eligible_for_promote else 1


def cmd_stages(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    reg = load_stages_registry(root)
    stages = reg.get("stages") or {}
    out: dict[str, object] = {"stages": []}
    for sid in VALID_STAGES:
        block = stages.get(sid) or {}
        entry: dict[str, object] = {
            "id": sid,
            "label_ko": block.get("label_ko", ""),
            "depends_on": block.get("depends_on", []),
            "typical_gates": block.get("typical_gates", []),
        }
        if args.project:
            project_dir = root / "projects" / args.project
            entry["groups"] = list_groups_in_stage(project_dir, sid)
        out["stages"].append(entry)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


def cmd_schedule(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    if args.project:
        project_dir = root / "projects" / args.project
        statuses = project_acquisition_status(project_dir)
        out = {
            "project_id": args.project,
            "items": [s.to_dict() for s in statuses],
            "due": [s.kind for s in statuses if s.due],
        }
    else:
        out = workspace_acquisition_status(root)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


def cmd_graph_spec(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    print(json.dumps(load_flow_spec(root), indent=2, ensure_ascii=False))
    return 0


def cmd_graph_start(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    try:
        out = start_session(
            root,
            graph_id=args.graph,
            mode=args.mode,
            project_id=args.project or "",
            stage=args.stage or "",
            group=args.group or "",
            user_skillset=getattr(args, "skillset", "") or "",
        )
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, indent=2, ensure_ascii=False))
        return 2
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


def cmd_node_guide(args: argparse.Namespace) -> int:
    import json as _json
    from pathlib import Path as _Path

    from soc_verify.node_guide import list_node_guides, load_registry
    from soc_verify.node_guide_wizard import add_node_from_dict, run_node_guide_wizard

    root = _Path(args.root).resolve()
    action = getattr(args, "node_guide_cmd", None) or "wizard"

    if action == "add":
        if not args.project:
            print(_json.dumps({"error": "--project required"}, indent=2))
            return 2
        if args.json:
            data = _json.loads(_Path(args.json).read_text(encoding="utf-8"))
            out = add_node_from_dict(root, args.project, data)
            print(_json.dumps(out, indent=2, ensure_ascii=False))
            return 0 if out.get("ok") else 1
        return run_node_guide_wizard(root, project_id=args.project, action="add", non_interactive=args.non_interactive)

    if action == "list":
        if not args.project:
            print(_json.dumps({"error": "--project required"}, indent=2))
            return 2
        reg = load_registry(root / "projects" / args.project)
        reg["nodes_detail"] = list_node_guides(root / "projects" / args.project)
        print(_json.dumps(reg, indent=2, ensure_ascii=False))
        return 0

    if action == "apply":
        from soc_verify.node_guide import materialize_all

        if not args.project:
            print(_json.dumps({"error": "--project required"}, indent=2))
            return 2
        results = materialize_all(root / "projects" / args.project, root=root)
        print(_json.dumps({"applied": len(results), "results": results}, indent=2, ensure_ascii=False))
        return 0

    return run_node_guide_wizard(
        root,
        project_id=args.project or "",
        action="add",
        non_interactive=args.non_interactive,
    )


def cmd_skill_list(args: argparse.Namespace) -> int:
    from soc_verify.skill_registry import list_skills

    root = Path(args.root).resolve()
    project_dir = root / "projects" / args.project
    skills = list_skills(project_dir, milestone=args.milestone or "")
    print(json.dumps({"project": args.project, "skills": skills}, indent=2, ensure_ascii=False))
    return 0


def cmd_skill_show(args: argparse.Namespace) -> int:
    from soc_verify.skill_registry import get_skill

    root = Path(args.root).resolve()
    project_dir = root / "projects" / args.project
    skill = get_skill(project_dir, args.skill_id)
    if not skill:
        print(json.dumps({"error": "not_found", "skill_id": args.skill_id}, indent=2))
        return 1
    print(json.dumps(skill, indent=2, ensure_ascii=False))
    return 0


def cmd_meta_innovation_trigger(args: argparse.Namespace) -> int:
    from soc_verify.schedule_triggers import request_immediate

    root = Path(args.root).resolve()
    project_dir = root / "projects" / args.project
    path = request_immediate(project_dir, meta_innovation=True)
    print(json.dumps({"ok": True, "schedule": str(path), "run_now": True}, indent=2))
    return 0


def cmd_meta_innovation_due(args: argparse.Namespace) -> int:
    from soc_verify.schedule_triggers import collect_due_triggers

    root = Path(args.root).resolve()
    project_dir = root / "projects" / args.project
    events = [e.strip() for e in (args.events or "").split(",") if e.strip()]
    due = collect_due_triggers(project_dir, pending_events=events, root=root)
    print(json.dumps({"project": args.project, "due": [d.to_dict() for d in due]}, indent=2, ensure_ascii=False))
    return 0


def cmd_pipeline_list(args: argparse.Namespace) -> int:
    from soc_verify.milestone_pipeline import list_pipelines, pipelines_for_milestone

    root = Path(args.root).resolve()
    if args.milestone:
        pipelines = pipelines_for_milestone(root, args.milestone)
    else:
        pipelines = list_pipelines(root)
    print(json.dumps({"pipelines": pipelines}, indent=2, ensure_ascii=False, default=str))
    return 0


def cmd_pipeline_compile(args: argparse.Namespace) -> int:
    from soc_verify.milestone_pipeline import compile_branch_graph, get_pipeline, write_compiled_pipeline

    root = Path(args.root).resolve()
    project_dir = root / "projects" / args.project
    pl = get_pipeline(root, args.pipeline_id, project_id=args.project)
    if not pl:
        print(json.dumps({"error": "pipeline_not_found", "id": args.pipeline_id}, indent=2))
        return 1
    path = write_compiled_pipeline(project_dir, pl)
    print(json.dumps({"compiled": str(path), "graph": compile_branch_graph(pl)}, indent=2, ensure_ascii=False))
    return 0


def cmd_skill_add(args: argparse.Namespace) -> int:
    from soc_verify.skill_registry import register_skill, register_skillset_from_text

    root = Path(args.root).resolve()
    project_dir = root / "projects" / args.project
    body = args.body or ""
    if args.file:
        body = Path(args.file).read_text(encoding="utf-8")
    if not body.strip():
        print(json.dumps({"error": "empty_body"}, indent=2))
        return 2
    if args.name:
        entry = register_skill(
            project_dir,
            name=args.name,
            body=body,
            milestone_ids=[m for m in (args.milestone or "").split(",") if m],
        )
        print(json.dumps({"registered": entry}, indent=2, ensure_ascii=False))
    else:
        entries = register_skillset_from_text(
            project_dir,
            body,
            default_milestone=args.milestone or "",
        )
        print(json.dumps({"registered": entries}, indent=2, ensure_ascii=False))
    return 0


def cmd_graph_status(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    print(json.dumps(session_status(root, args.session), indent=2, ensure_ascii=False, default=str))
    return 0


def cmd_graph_tick(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    print(json.dumps(session_tick(root, args.session), indent=2, ensure_ascii=False, default=str))
    return 0


def cmd_graph_resume(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    print(json.dumps(session_resume(root, args.session), indent=2, ensure_ascii=False, default=str))
    return 0


def cmd_graph_invoke_llm(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    print(json.dumps(session_invoke_llm(root, args.session), indent=2, ensure_ascii=False, default=str))
    return 0


def cmd_graph_sandbox(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    out = session_sandbox(
        root,
        args.session,
        action=args.action,
        tool=args.tool or "",
        path=args.path or "",
        content=args.content,
    )
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("ok", True) and "error" not in out else 1


def cmd_graph_serve(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    serve_graph_api(root, host=args.host, port=args.port)
    return 0


def cmd_graph_drive(args: argparse.Namespace) -> int:
    """Run graph session until END (platform nodes auto; LLM nodes invoke company API)."""
    root = Path(args.root).resolve()
    if not args.session:
        if not (args.project and args.stage and args.group):
            print(json.dumps({"error": "provide --session or --project --stage --group"}, indent=2))
            return 2
        started = start_session(
            root,
            graph_id="verify_group",
            project_id=args.project,
            stage=args.stage,
            group=args.group,
        )
        session_id = started["session_id"]
    else:
        session_id = args.session
    result = run_until_done(root, session_id, max_ticks=args.max_ticks)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    verdict = (result.get("state") or {}).get("verdict", "FAIL")
    return 0 if verdict == "PASS" else 1


def cmd_feedback(args: argparse.Namespace) -> int:
    """User rubric score 1–5 for a completed run (optional human feedback)."""
    root = Path(args.root).resolve()
    project_dir = root / "projects" / args.project
    run_dir = project_dir / "runs" / args.run_id
    if not run_dir.is_dir():
        print(json.dumps({"error": f"run not found: {run_dir}"}, indent=2))
        return 2
    path = write_user_feedback(
        run_dir,
        overall_score=int(args.score),
        comment=args.comment or "",
        reviewer=args.reviewer or "user",
    )
    print(json.dumps({"ok": True, "path": str(path)}, indent=2))
    return 0


def cmd_export_paper(args: argparse.Namespace) -> int:
    from soc_verify.paper_export import export_paper

    root = Path(args.root).resolve()
    out_raw = args.out or f"exports/{args.campaign}"
    out = Path(out_raw)
    if not out.is_absolute():
        out = root / out
    result = export_paper(root, args.campaign, out)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def cmd_paper_status(args: argparse.Namespace) -> int:
    from soc_verify.experiment import evaluation_progress, find_runs_for_campaign

    root = Path(args.root).resolve()
    campaign = args.campaign
    progress = evaluation_progress(root, campaign)
    runs = find_runs_for_campaign(root, campaign)
    print(
        json.dumps(
            {
                "campaign": campaign,
                "tagged_runs": len(runs),
                "evaluation_progress": progress,
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )
    return 0


def cmd_paper_progress(args: argparse.Namespace) -> int:
    from soc_verify.paper_progress import resolve_paper_project, sync_paper_progress

    root = Path(args.root).resolve()
    campaign = args.campaign
    project_id = resolve_paper_project(root, campaign, getattr(args, "project", "") or "")
    if not project_id:
        print(json.dumps({"error": "no project — pass --project ID"}, indent=2))
        return 2
    result = sync_paper_progress(
        root,
        project_id,
        campaign,
        write_llm_prompt=not args.no_prompt,
        force_mechanical_judgment=args.refresh_judgment,
    )
    if args.format == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(
            f"Paper progress: {result.get('overall_percent')}% — "
            f"{result.get('progress_md')} (campaign {campaign})"
        )
    return 0


def cmd_paper_readiness(args: argparse.Namespace) -> int:
    from soc_verify.paper_readiness import (
        assess_paper_readiness,
        format_readiness_summary,
        write_readiness_report,
    )

    root = Path(args.root).resolve()
    campaign = args.campaign
    report = assess_paper_readiness(root, campaign)

    if args.format == "json":
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    else:
        print(format_readiness_summary(report))

    if args.out:
        out = Path(args.out)
        if not out.is_absolute():
            out = root / out
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.suffix == ".md":
            out.write_text(format_readiness_summary(report), encoding="utf-8")
            json_path = out.with_suffix(".json")
        else:
            json_path = out
            out = out.with_suffix(".md")
            out.write_text(format_readiness_summary(report), encoding="utf-8")
        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n(written: {json_path}, {out})", file=__import__("sys").stderr)
    elif args.write:
        path = write_readiness_report(root, campaign)
        md_path = path.with_suffix(".md")
        md_path.write_text(format_readiness_summary(report), encoding="utf-8")
        print(f"\n(written: {path}, {md_path})", file=__import__("sys").stderr)

    if getattr(args, "sync_progress", False) or getattr(args, "project", None):
        from soc_verify.paper_progress import resolve_paper_project, sync_paper_progress

        pid = resolve_paper_project(root, campaign, getattr(args, "project", "") or "")
        if pid:
            sync_paper_progress(root, pid, campaign, write_llm_prompt=True)
            print(f"\n(vault progress: projects/{pid}/knowledge/obsidian/06-paper/PROGRESS.md)", file=__import__("sys").stderr)

    return 0


def cmd_paper_suggest(args: argparse.Namespace) -> int:
    from soc_verify.paper_factory import format_suggestions_text, suggest_verify_commands
    from soc_verify.paper_readiness import assess_paper_readiness

    root = Path(args.root).resolve()
    campaign = args.campaign
    readiness = assess_paper_readiness(root, campaign)
    suggestions = suggest_verify_commands(
        root,
        campaign,
        hypothesis=args.hypothesis,
        max_per_condition=args.max,
        readiness=readiness,
    )
    if args.format == "json":
        print(
            json.dumps(
                {
                    "campaign": campaign,
                    "overall_percent": readiness.get("overall_percent"),
                    "suggestions": [s.to_command(root) for s in suggestions],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        print(
            format_suggestions_text(
                suggestions,
                root=root,
                campaign=campaign,
                overall_percent=float(readiness.get("overall_percent", 0)),
                verdict=str(readiness.get("verdict", "")),
            )
        )
    return 0


def cmd_paper_run(args: argparse.Namespace) -> int:
    from soc_verify.paper_factory import format_factory_summary, run_factory

    root = Path(args.root).resolve()
    report = run_factory(
        root,
        args.campaign,
        hypothesis=args.hypothesis,
        write=args.write,
        export=args.export,
        max_suggestions=args.max,
    )
    if args.format == "json":
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False, default=str))
    else:
        print(format_factory_summary(report))
    return 0 if report.paper_ready else 1


def cmd_experiment_tag(args: argparse.Namespace) -> int:
    from soc_verify.experiment import register_campaign_run, resolve_experiment_tags, write_experiment_run

    root = Path(args.root).resolve()
    project_dir = root / "projects" / args.project
    run_dir = project_dir / "runs" / args.run_id
    if not run_dir.is_dir():
        print(json.dumps({"error": f"run not found: {run_dir}"}, indent=2))
        return 2
    tags = resolve_experiment_tags(
        root,
        campaign=args.campaign,
        condition=args.condition or "treatment_full",
        hypothesis=args.hypothesis or "",
        notes=args.notes or "",
    )
    write_experiment_run(run_dir, tags)
    register_campaign_run(
        root,
        tags,
        run_meta={
            "run_id": args.run_id,
            "project_id": args.project,
            "graph_id": "manual_tag",
        },
    )
    print(json.dumps({"ok": True, "experiment_run": tags}, indent=2, ensure_ascii=False))
    return 0


def cmd_telemetry(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    baseline = ensure_platform_baseline(root, trigger="cli_telemetry")
    stats = load_cumulative_stats(root)
    from soc_verify.platform_telemetry import code_change_summary

    print(
        json.dumps(
            {
                "baseline": baseline,
                "cumulative": stats,
                "code_changes": code_change_summary(root),
            },
            indent=2,
            default=str,
        )
    )
    return 0


def cmd_active(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    today = date.today().isoformat()
    active = load_active_projects(root / "registry", today)
    print(json.dumps({"as_of": today, "active": active}, indent=2))
    return 0


def cmd_milestone_plans(args: argparse.Namespace) -> int:
    from soc_verify.milestone_plans import list_plans, load_plan_index

    root = Path(args.root).resolve()
    idx = load_plan_index(root)
    print(
        json.dumps(
            {"default_plan": idx.get("default_plan"), "plans": list_plans(root)},
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def cmd_milestone_show(args: argparse.Namespace) -> int:
    from soc_verify.milestone_plans import load_plan

    root = Path(args.root).resolve()
    plan = load_plan(root, args.plan)
    if not plan:
        print(json.dumps({"error": f"plan not found: {args.plan}"}, indent=2))
        return 2
    print(json.dumps(plan, indent=2, ensure_ascii=False, default=str))
    return 0


def cmd_milestone_validate(args: argparse.Namespace) -> int:
    from soc_verify.config import load_user_config
    from soc_verify.milestone_plans import validate_project_schedule

    root = Path(args.root).resolve()
    config = load_user_config(root).raw if (root / "config.json").is_file() else None
    project_dir = root / "projects" / args.project
    if not project_dir.is_dir():
        print(json.dumps({"error": f"project not found: {args.project}"}, indent=2))
        return 2
    result = validate_project_schedule(root, project_dir, config=config)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("valid") else 1


def cmd_knowledge_bootstrap_paper_skills(args: argparse.Namespace) -> int:
    from soc_verify.paper_intake_skills import bootstrap_paper_intake_skills

    root = Path(args.root).resolve()
    project_dir = root / "projects" / args.project
    if not project_dir.is_dir():
        print(json.dumps({"error": f"project not found: {args.project}"}, indent=2))
        return 2
    result = bootstrap_paper_intake_skills(project_dir, root, force=args.force)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


def cmd_knowledge_collect(args: argparse.Namespace) -> int:
    from soc_verify.knowledge_intake import collect_knowledge_bundle

    root = Path(args.root).resolve()
    bundle = collect_knowledge_bundle(root, args.project)
    print(json.dumps({"ok": True, "project_id": args.project, "sources": len(bundle.get("sources", []))}, indent=2))
    return 0


def cmd_knowledge_normalize(args: argparse.Namespace) -> int:
    from soc_verify.knowledge_intake import normalize_to_obsidian

    root = Path(args.root).resolve()
    result = normalize_to_obsidian(root, args.project, force=args.force)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


def cmd_knowledge_sources(args: argparse.Namespace) -> int:
    from soc_verify.knowledge_intake import add_source_interactive, load_sources, seed_sources_from_discovered

    root = Path(args.root).resolve()
    project_dir = root / "projects" / args.project
    if not project_dir.is_dir():
        print(json.dumps({"error": f"project not found: {args.project}"}, indent=2))
        return 2
    if args.seed:
        seed_sources_from_discovered(project_dir)
    if args.type and args.location:
        add_source_interactive(
            project_dir,
            source_type=args.type,
            location=args.location,
            label=args.label or args.type,
            root=root,
        )
    data = load_sources(project_dir)
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return 0


def cmd_setup(args: argparse.Namespace) -> int:
    from soc_verify.setup_wizard import format_setup_summary, run_setup_wizard, setup_status

    root = Path(args.root).resolve()
    if args.status:
        st = setup_status(root)
        if args.json:
            print(json.dumps(st, indent=2, ensure_ascii=False))
        else:
            print(format_setup_summary(st))
        return 0 if st.get("setup_complete") else 1

    return run_setup_wizard(
        root,
        section=args.section,
        non_interactive=args.non_interactive,
        reset=args.reset,
    )


def main() -> int:
    p = argparse.ArgumentParser(prog="soc-verify")
    p.add_argument("--root", default=".", help="soc-verify-agent root")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="Orchestrator: acquisition due + pending verify (workspace)")
    r.add_argument("--thread", default="orchestrator")
    r.set_defaults(func=cmd_run)

    v = sub.add_parser("verify", help="Orchestrator → verify_group (single job)")
    v.add_argument("project", help="project id")
    v.add_argument("stage", help="verification stage (sanity|consistency|static|simulation|regression)")
    v.add_argument("group", help="verification group name")
    v.add_argument("--thread", default="default")
    v.add_argument("--campaign", default="", help="Paper campaign id (e.g. paper_eval_2026)")
    v.add_argument("--condition", default="", help="Experiment condition (control|treatment_full)")
    v.add_argument("--hypothesis", default="", help="Hypothesis id (e.g. H1)")
    v.set_defaults(func=cmd_verify)

    st = sub.add_parser("stages", help="List verification stages (optional: groups per project)")
    st.add_argument("--project", default=None, help="project id to list groups per stage")
    st.set_defaults(func=cmd_stages)

    t = sub.add_parser("tag-replace", help="Mandatory tag replace + cascade invalidation")
    t.add_argument("project")
    t.add_argument("tag")
    t.add_argument("--clone", default=None)
    t.set_defaults(func=cmd_tag_replace)

    te = sub.add_parser("trust-eval", help="Evaluate script trust")
    te.add_argument("project")
    te.add_argument("script", help="path under project e.g. ops/groups/foo.py")
    te.add_argument("--run-id", default="trust-eval")
    te.set_defaults(func=cmd_trust_eval)

    sch = sub.add_parser("schedule", help="Acquisition dates and refresh due status")
    sch.add_argument("--project", default=None, help="single project id")
    sch.set_defaults(func=cmd_schedule)

    a = sub.add_parser("active", help="List active projects for today")
    a.set_defaults(func=cmd_active)

    ms = sub.add_parser("milestone", help="Milestone plans (culture-specific phase ladders)")
    mss = ms.add_subparsers(dest="milestone_cmd", required=True)
    mpl = mss.add_parser("plans", help="List available milestone plans")
    mpl.set_defaults(func=cmd_milestone_plans)
    msh = mss.add_parser("show", help="Show one plan definition")
    msh.add_argument("--plan", required=True)
    msh.set_defaults(func=cmd_milestone_show)
    msv = mss.add_parser("validate", help="Validate project state + group manifests vs plan")
    msv.add_argument("project")
    msv.set_defaults(func=cmd_milestone_validate)

    su = sub.add_parser("setup", help="설정 허브 TUI — 초기·변경 모두 메뉴에서 섹션 선택")
    su.add_argument(
        "section",
        nargs="?",
        default=None,
        choices=[
            "llm", "workspace", "milestone", "project", "knowledge",
            "schedules", "nodes", "paper", "platform",
        ],
        help="섹션 직행 (기본: 설정 허브 메뉴)",
    )
    su.add_argument("--status", action="store_true", help="Show setup checklist progress")
    su.add_argument("--json", action="store_true", help="JSON output (with --status)")
    su.add_argument("--reset", action="store_true", help="Clear setup progress")
    su.add_argument("--non-interactive", action="store_true", help="Print guidance only (no TTY)")
    su.set_defaults(func=cmd_setup)

    kn = sub.add_parser("knowledge", help="Intake Confluence/wiki/md → uniform Obsidian MD (LLM)")
    knsub = kn.add_subparsers(dest="knowledge_cmd", required=True)
    kns = knsub.add_parser("sources", help="List/add knowledge_sources.yaml")
    kns.add_argument("project")
    kns.add_argument("--seed", action="store_true", help="Seed from discovered.yaml")
    kns.add_argument("--type", default=None, choices=["confluence", "wiki", "markdown", "markdown_dir", "doc", "url"])
    kns.add_argument("--location", default=None, help="URL or path")
    kns.add_argument("--label", default="")
    kns.set_defaults(func=cmd_knowledge_sources)
    knb = knsub.add_parser(
        "bootstrap-paper-skills",
        help="Install paper-intake SKILL.md templates (논문급 수집·정리)",
    )
    knb.add_argument("project")
    knb.add_argument("--force", action="store_true", help="Overwrite existing paper intake skills")
    knb.set_defaults(func=cmd_knowledge_bootstrap_paper_skills)
    knc = knsub.add_parser("collect", help="Gather sources → knowledge_bundle.json")
    knc.add_argument("project")
    knc.set_defaults(func=cmd_knowledge_collect)
    knn = knsub.add_parser("normalize", help="LLM → templates/obsidian/projects/{id}.md")
    knn.add_argument("project")
    knn.add_argument("--force", action="store_true", help="Re-collect before normalize")
    knn.set_defaults(func=cmd_knowledge_normalize)

    fb = sub.add_parser("feedback", help="User score 1–5 for a run (human rubric, optional)")
    fb.add_argument("project")
    fb.add_argument("run_id")
    fb.add_argument("--score", type=int, required=True, help="1–5 overall satisfaction")
    fb.add_argument("--comment", default="")
    fb.add_argument("--reviewer", default="user")
    fb.set_defaults(func=cmd_feedback)

    tel = sub.add_parser("telemetry", help="Platform baseline + cumulative success/trust/code edits")
    tel.set_defaults(func=cmd_telemetry)

    ep = sub.add_parser("export-paper", help="Export campaign runs → CSV + Methods (paper factory)")
    ep.add_argument("--campaign", required=True)
    ep.add_argument(
        "--out",
        default=None,
        help="Output directory under --root (default: exports/<campaign>)",
    )
    ep.set_defaults(func=cmd_export_paper)

    ps = sub.add_parser("paper", help="Paper evaluation campaign status")
    pss = ps.add_subparsers(dest="paper_cmd", required=True)
    pstat = pss.add_parser("status", help="Evaluation manifest progress for campaign")
    pstat.add_argument("--campaign", default="paper_eval_2026")
    pstat.set_defaults(func=cmd_paper_status)

    pprog = pss.add_parser("progress", help="논문 퍼즐 %% + LLM judgment → 06-paper/PROGRESS.md")
    pprog.add_argument("--project", default="", help="Project id (auto-detect from campaign runs if omitted)")
    pprog.add_argument("--campaign", default="paper_eval_2026")
    pprog.add_argument("--write", action="store_true", help="Sync vault PROGRESS.md (default when invoked)")
    pprog.add_argument("--format", choices=["summary", "json"], default="summary")
    pprog.add_argument("--no-prompt", action="store_true", help="Skip paper_progress_prompt.json")
    pprog.add_argument("--refresh-judgment", action="store_true", help="Overwrite judgment with mechanical only")
    pprog.set_defaults(func=cmd_paper_progress)

    pread = pss.add_parser("readiness", help="Paper readiness %% + gaps vs typical systems papers")
    pread.add_argument("--campaign", default="paper_eval_2026")
    pread.add_argument("--project", default="", help="Also sync 06-paper/PROGRESS.md for this project")
    pread.add_argument("--sync-progress", action="store_true", help="Sync vault progress diagram")
    pread.add_argument("--format", choices=["summary", "json"], default="summary")
    pread.add_argument("--out", default=None, help="Write report (.json or .md; companion file auto-written)")
    pread.add_argument("--write", action="store_true", help="Write to exports/<campaign>/paper_readiness.*")
    pread.set_defaults(func=cmd_paper_readiness)

    psug = pss.add_parser("suggest", help="Suggest verify commands for paper data gaps")
    psug.add_argument("--campaign", default="paper_eval_2026")
    psug.add_argument("--hypothesis", default="H1")
    psug.add_argument("--max", type=int, default=3)
    psug.add_argument("--format", choices=["text", "json"], default="text")
    psug.set_defaults(func=cmd_paper_suggest)

    prun = pss.add_parser("run", help="Full paper factory report (assess + suggest + optional export)")
    prun.add_argument("--campaign", default="paper_eval_2026")
    prun.add_argument("--hypothesis", default="H1")
    prun.add_argument("--write", action="store_true")
    prun.add_argument("--export", action="store_true")
    prun.add_argument("--max", type=int, default=3)
    prun.add_argument("--format", choices=["summary", "json"], default="summary")
    prun.set_defaults(func=cmd_paper_run)

    ex = sub.add_parser("experiment", help="Tag an existing run for paper campaign")
    ex.add_argument("project")
    ex.add_argument("run_id")
    ex.add_argument("--campaign", required=True)
    ex.add_argument("--condition", default="treatment_full")
    ex.add_argument("--hypothesis", default="")
    ex.add_argument("--notes", default="")
    ex.set_defaults(func=cmd_experiment_tag)

    g = sub.add_parser("graph", help="LangGraph flow spec + API (LLM driver)")
    gsub = g.add_subparsers(dest="graph_cmd", required=True)

    gs = gsub.add_parser("spec", help="Print graph_flow_spec.yaml (LLM reads this)")
    gs.set_defaults(func=cmd_graph_spec)

    gst = gsub.add_parser("start", help="Start graph session")
    gst.add_argument(
        "--graph",
        default="verify_group",
        choices=["verify_group", "orchestrator", "setup_group", "meta_innovation_loop"],
    )
    gst.add_argument("--mode", default="single_verify")
    gst.add_argument("--project", default=None)
    gst.add_argument("--stage", default=None)
    gst.add_argument("--group", default=None)
    gst.add_argument("--skillset", default="", help="User verification skillset text (setup_group)")
    gst.set_defaults(func=cmd_graph_start)

    ng = sub.add_parser("node-guide", help="User-defined node TUI — location + content, auto-write files")
    ngsub = ng.add_subparsers(dest="node_guide_cmd", required=False)
    ngw = ngsub.add_parser("wizard", help="Interactive add node (default)")
    ngw.add_argument("--project", default="")
    ngw.add_argument("--non-interactive", action="store_true")
    ngw.set_defaults(node_guide_cmd="wizard")
    nga = ngsub.add_parser("add", help="Add one node (TUI or --json)")
    nga.add_argument("--project", required=True)
    nga.add_argument("--json", default="", help="NodeGuideEntry JSON file")
    nga.add_argument("--non-interactive", action="store_true")
    nga.set_defaults(node_guide_cmd="add")
    ngl = ngsub.add_parser("list", help="List user node guides")
    ngl.add_argument("--project", required=True)
    ngl.set_defaults(node_guide_cmd="list")
    ngap = ngsub.add_parser("apply", help="Re-materialize all guides to disk")
    ngap.add_argument("--project", required=True)
    ngap.set_defaults(node_guide_cmd="apply")
    ng.add_argument("--project", default="")
    ng.add_argument("--non-interactive", action="store_true")
    ng.set_defaults(func=cmd_node_guide, node_guide_cmd="wizard")

    sk = sub.add_parser("skill", help="Project verification skill registry")
    sksub = sk.add_subparsers(dest="skill_cmd", required=True)
    skl = sksub.add_parser("list", help="List registered skills")
    skl.add_argument("project")
    skl.add_argument("--milestone", default="")
    skl.set_defaults(func=cmd_skill_list)
    sks = sksub.add_parser("show", help="Show one skill with body")
    sks.add_argument("project")
    sks.add_argument("skill_id")
    sks.set_defaults(func=cmd_skill_show)
    ska = sksub.add_parser("add", help="Register skill or parse skillset text")
    ska.add_argument("project")
    ska.add_argument("--name", default="", help="Single skill name (omit to parse blocks)")
    ska.add_argument("--body", default="", help="Skill markdown body")
    ska.add_argument("--file", default="", help="Read body from file")
    ska.add_argument("--milestone", default="", help="Milestone id or comma-separated list")
    ska.set_defaults(func=cmd_skill_add)

    mil = sub.add_parser("meta-innovation", help="Meta Innovation Loop — BECI intervention")
    milsub = mil.add_subparsers(dest="mil_cmd", required=True)
    milt = milsub.add_parser("trigger", help="Request immediate meta innovation run")
    milt.add_argument("project")
    milt.set_defaults(func=cmd_meta_innovation_trigger)
    mild = milsub.add_parser("due", help="List due triggers (cron/events)")
    mild.add_argument("project")
    mild.add_argument("--events", default="", help="Comma-separated pending events")
    mild.set_defaults(func=cmd_meta_innovation_due)

    pln = sub.add_parser("pipeline", help="Milestone pipelines → branch LangGraph specs")
    plsub = pln.add_subparsers(dest="pipeline_cmd", required=True)
    pll = plsub.add_parser("list", help="List milestone pipelines")
    pll.add_argument("--milestone", default="")
    pll.set_defaults(func=cmd_pipeline_list)
    plc = plsub.add_parser("compile", help="Compile pipeline to project meta/pipeline_graphs/")
    plc.add_argument("project")
    plc.add_argument("pipeline_id")
    plc.set_defaults(func=cmd_pipeline_compile)

    gst2 = gsub.add_parser("status", help="Session status + current node spec")
    gst2.add_argument("--session", required=True)
    gst2.set_defaults(func=cmd_graph_status)

    gti = gsub.add_parser("tick", help="Advance one graph node")
    gti.add_argument("--session", required=True)
    gti.set_defaults(func=cmd_graph_tick)

    gr = gsub.add_parser("resume", help="LLM completed node → advance (alias tick)")
    gr.add_argument("--session", required=True)
    gr.set_defaults(func=cmd_graph_resume)

    gil = gsub.add_parser("invoke-llm", help="Graph calls company LLM API for current node")
    gil.add_argument("--session", required=True)
    gil.set_defaults(func=cmd_graph_invoke_llm)

    gsb = gsub.add_parser("sandbox", help="Node-scoped tool/write sandbox (current node only)")
    gsb.add_argument("--session", required=True)
    gsb.add_argument(
        "--action",
        default="capabilities",
        choices=["capabilities", "tool", "validate_write", "write"],
    )
    gsb.add_argument("--tool", default=None)
    gsb.add_argument("--path", default=None)
    gsb.add_argument("--content", default=None)
    gsb.set_defaults(func=cmd_graph_sandbox)

    gd = gsub.add_parser("drive", help="Auto tick until finished")
    gd.add_argument("--session", default=None)
    gd.add_argument("--project", default=None)
    gd.add_argument("--stage", default=None)
    gd.add_argument("--group", default=None)
    gd.add_argument("--max-ticks", type=int, default=50)
    gd.set_defaults(func=cmd_graph_drive)

    gsv = gsub.add_parser("serve", help="HTTP Graph API for company LLM")
    gsv.add_argument("--host", default="127.0.0.1")
    gsv.add_argument("--port", type=int, default=8765)
    gsv.set_defaults(func=cmd_graph_serve)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())