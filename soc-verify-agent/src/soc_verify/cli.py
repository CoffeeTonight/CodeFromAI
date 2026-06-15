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
from soc_verify.graphs.orchestrator import run_orchestrator
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
    result = run_orchestrator(root, mode="workspace", thread_id=args.thread)
    _print_orchestrator_result(result)
    verdict = result.get("verdict", "FAIL")
    return 0 if verdict == "PASS" else 1


def cmd_verify(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
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
    out = start_session(
        root,
        graph_id=args.graph,
        mode=args.mode,
        project_id=args.project or "",
        stage=args.stage or "",
        group=args.group or "",
    )
    print(json.dumps(out, indent=2, ensure_ascii=False))
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


def cmd_active(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    today = date.today().isoformat()
    active = load_active_projects(root / "registry", today)
    print(json.dumps({"as_of": today, "active": active}, indent=2))
    return 0


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

    g = sub.add_parser("graph", help="LangGraph flow spec + API (LLM driver)")
    gsub = g.add_subparsers(dest="graph_cmd", required=True)

    gs = gsub.add_parser("spec", help="Print graph_flow_spec.yaml (LLM reads this)")
    gs.set_defaults(func=cmd_graph_spec)

    gst = gsub.add_parser("start", help="Start graph session")
    gst.add_argument("--graph", default="verify_group", choices=["verify_group", "orchestrator"])
    gst.add_argument("--mode", default="single_verify")
    gst.add_argument("--project", default=None)
    gst.add_argument("--stage", default=None)
    gst.add_argument("--group", default=None)
    gst.set_defaults(func=cmd_graph_start)

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