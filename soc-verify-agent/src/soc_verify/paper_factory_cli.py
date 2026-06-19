"""Standalone `paper-factory` CLI — works without Grok."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from soc_verify.experiment import evaluation_progress, find_runs_for_campaign
from soc_verify.paper_factory import (
    find_repo_root,
    format_factory_summary,
    format_readiness_summary,
    format_suggestions_text,
    run_factory,
    suggest_verify_commands,
)
from soc_verify.paper_export import export_paper
from soc_verify.paper_readiness import assess_paper_readiness, write_readiness_report


def _resolve_root(args: argparse.Namespace) -> Path:
    if args.root:
        return Path(args.root).resolve()
    return find_repo_root()


def cmd_assess(args: argparse.Namespace) -> int:
    root = _resolve_root(args)
    report = assess_paper_readiness(root, args.campaign)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    else:
        print(format_readiness_summary(report))
    if args.write:
        path = write_readiness_report(root, args.campaign)
        md = path.with_suffix(".md")
        md.write_text(format_readiness_summary(report), encoding="utf-8")
        print(f"# written: {path}\n# written: {md}", file=sys.stderr)
    return 0 if report.get("paper_ready") else 1


def cmd_suggest(args: argparse.Namespace) -> int:
    root = _resolve_root(args)
    readiness = assess_paper_readiness(root, args.campaign)
    suggestions = suggest_verify_commands(
        root,
        args.campaign,
        hypothesis=args.hypothesis,
        max_per_condition=args.max,
        readiness=readiness,
    )
    if args.json:
        payload = {
            "campaign": args.campaign,
            "overall_percent": readiness.get("overall_percent"),
            "suggestions": [s.to_command(root) for s in suggestions],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(
            format_suggestions_text(
                suggestions,
                root=root,
                campaign=args.campaign,
                overall_percent=float(readiness.get("overall_percent", 0)),
                verdict=str(readiness.get("verdict", "")),
            )
        )
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    root = _resolve_root(args)
    out = Path(args.out) if args.out else root / "exports" / args.campaign
    if not out.is_absolute():
        out = root / out
    result = export_paper(root, args.campaign, out)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    root = _resolve_root(args)
    progress = evaluation_progress(root, args.campaign)
    runs = find_runs_for_campaign(root, args.campaign)
    print(
        json.dumps(
            {"campaign": args.campaign, "tagged_runs": len(runs), "evaluation_progress": progress},
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    root = _resolve_root(args)
    report = run_factory(
        root,
        args.campaign,
        hypothesis=args.hypothesis,
        write=args.write,
        export=args.export,
        max_suggestions=args.max,
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False, default=str))
    else:
        print(format_factory_summary(report))
    return 0 if report.paper_ready else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="paper-factory",
        description="Paper factory — readiness %%, gaps, verify suggestions, export (no Grok required)",
    )
    p.add_argument("--root", default=None, help="soc-verify-agent root (auto-detect from cwd)")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("assess", help="Paper readiness %% and gaps")
    a.add_argument("--campaign", default="paper_eval_2026")
    a.add_argument("--json", action="store_true")
    a.add_argument("--write", action="store_true")
    a.set_defaults(func=cmd_assess)

    s = sub.add_parser("suggest", help="Suggest verify commands for missing data")
    s.add_argument("--campaign", default="paper_eval_2026")
    s.add_argument("--hypothesis", default="H1")
    s.add_argument("--max", type=int, default=3, help="Max commands per condition")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_suggest)

    e = sub.add_parser("export", help="Export CSV + Methods + readiness")
    e.add_argument("--campaign", required=True)
    e.add_argument("--out", default=None)
    e.set_defaults(func=cmd_export)

    st = sub.add_parser("status", help="Evaluation manifest gate progress")
    st.add_argument("--campaign", default="paper_eval_2026")
    st.set_defaults(func=cmd_status)

    r = sub.add_parser("run", help="Full report: assess + suggest + write (+ export if ready)")
    r.add_argument("--campaign", default="paper_eval_2026")
    r.add_argument("--hypothesis", default="H1")
    r.add_argument("--write", action="store_true", help="Write readiness + suggested_commands.sh")
    r.add_argument("--export", action="store_true", help="Force export-paper")
    r.add_argument("--max", type=int, default=3)
    r.add_argument("--json", action="store_true")
    r.set_defaults(func=cmd_run)

    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())