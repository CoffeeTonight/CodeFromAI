#!/usr/bin/env python3
"""hch-index — build SQLite hierarchy DB from .f filelist."""

from __future__ import annotations

import argparse
import os
import sys

from hch.engine.availability import check_engine
from hch.index.loader import build_index_from_filelist


def _parse_tops(args):
    if args.tops:
        tops = [t.strip() for t in args.tops.split(",") if t.strip()]
        return (tops[0] if tops else None, tops or None)
    if args.top:
        return args.top, [args.top]
    return None, None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Index Verilog hierarchy to SQLite (pyslang)")
    ap.add_argument("filelist", help="Top .f filelist")
    ap.add_argument("-o", "--output", default="design.hch.db", help="Output SQLite path")
    ap.add_argument("--top", default=None, help="Top module for hierarchy flatten")
    ap.add_argument(
        "--tops",
        default=None,
        help="Comma-separated top modules (overrides single --top flatten roots)",
    )
    ap.add_argument(
        "--elaborate",
        action="store_true",
        help="Tier E: use pyslang elaboration (generate/ifdef resolved)",
    )
    ap.add_argument(
        "--batch-size",
        type=int,
        default=0,
        help="Sources per pyslang batch (0=all at once). Enables checkpoint when >0",
    )
    ap.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Resume from checkpoint_files in existing DB",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Ignore checkpoint and rebuild module/instance tables",
    )
    ap.add_argument(
        "--path-hierarchy",
        choices=("auto", "on", "off"),
        default="auto",
        help="Synthetic u_* path layout: auto (detect), on, or off",
    )
    ap.add_argument(
        "--elab-instance-cap",
        type=int,
        default=50_000,
        help="Max elaborated instances (Tier E); meta when truncated",
    )
    ap.add_argument(
        "--no-elab-fast",
        action="store_true",
        help="Tier E: parse full filelist for ingest (disable closure-fast path)",
    )
    ap.add_argument(
        "--elab-deep",
        choices=("auto", "hybrid", "shallow", "closure"),
        default="auto",
        help="Deep synthetic: auto=path+shallow slang hybrid, shallow=8-file only, closure=pruned slang only",
    )
    ap.add_argument(
        "--index-cwd",
        default=None,
        metavar="DIR",
        help="Run directory for -F filelists (default: parent of top .f, or HCH_INDEX_CWD)",
    )
    ap.add_argument(
        "--ifdef-compare",
        action="store_true",
        help="Compare instance sets: filelist defines vs --ifdef-alt",
    )
    ap.add_argument(
        "--ifdef-alt",
        default="",
        help="Extra defines for ifdef compare, e.g. USE_ALT=1,FOO=2",
    )
    ap.add_argument(
        "--filelist-diff",
        metavar="OTHER.f",
        default=None,
        help="Compare primary filelist with another; store filelist_diff_json meta",
    )
    ap.add_argument(
        "--variant",
        action="append",
        default=[],
        help="Preprocessor variant NAME=DEFINE,... (repeatable); indexes into one DB",
    )
    ap.add_argument(
        "--variant-compare",
        metavar="A,B",
        default=None,
        help="After --variant indexing, diff instance paths between variants A and B",
    )
    ap.add_argument(
        "--variant-dir",
        metavar="DIR",
        default=None,
        help="With --variant: also write one .hch.db per variant under DIR (ifdef multi-DB)",
    )
    ap.add_argument(
        "--export-json",
        metavar="PATH",
        help="Write DQL-ready instances JSON after indexing",
    )
    args = ap.parse_args(argv)

    index_cwd = args.index_cwd or os.environ.get("HCH_INDEX_CWD") or None
    if args.elaborate and args.elab_deep == "closure":
        print(
            "WARNING: --elab-deep closure runs slang on a large pruned closure; "
            "designs with duplicate module names often fail. Prefer hybrid (default) or shallow.",
            file=sys.stderr,
        )

    status = check_engine()
    if not status.available:
        print(f"ERROR: {status.message}", file=sys.stderr)
        return 2

    top, tops = _parse_tops(args)
    variants = None
    if args.variant:
        from hch.index.variant_index import parse_variant_spec

        variants = [parse_variant_spec(v) for v in args.variant]
    variant_compare = None
    if args.variant_compare:
        parts = [p.strip() for p in args.variant_compare.split(",") if p.strip()]
        if len(parts) == 2:
            variant_compare = (parts[0], parts[1])
    store = build_index_from_filelist(
        args.filelist,
        args.output,
        top_module=top,
        top_modules=tops,
        elaborate=args.elaborate,
        batch_size=args.batch_size,
        resume=args.resume,
        force=args.force,
        path_hierarchy_mode=args.path_hierarchy,
        elab_instance_cap=args.elab_instance_cap,
        elab_fast=not args.no_elab_fast,
        elab_deep=args.elab_deep,
        ifdef_compare=args.ifdef_compare,
        ifdef_alt=args.ifdef_alt or None,
        filelist_diff=args.filelist_diff,
        variants=variants,
        variant_compare=variant_compare,
        variant_dir=args.variant_dir,
        index_cwd=index_cwd,
    )
    n = store.count_instances()
    if args.export_json:
        import json
        from pathlib import Path

        data = store.export_instance_dicts()
        Path(args.export_json).write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"Exported {len(data)} instances -> {args.export_json}")
    store.close()
    print(f"Indexed {n} instances -> {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())