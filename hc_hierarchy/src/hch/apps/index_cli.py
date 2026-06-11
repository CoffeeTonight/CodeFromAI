#!/usr/bin/env python3
"""hch-index — build SQLite hierarchy DB from .f filelist."""

from __future__ import annotations

import argparse
import os
import sys

from hch.apps.help_text import INDEX_HELP_EPILOG
from hch.apps.index_progress import IndexProgressReporter, progress_stderr_guard
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
    ap = argparse.ArgumentParser(
        description="Index Verilog/SystemVerilog hierarchy from a .f filelist into SQLite",
        epilog=INDEX_HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    io = ap.add_argument_group("filelist & output")
    io.add_argument("filelist", help="Top .f filelist path")
    io.add_argument(
        "-o",
        "--output",
        default="design.hch.db",
        help="Output SQLite path (default: design.hch.db)",
    )
    io.add_argument(
        "--index-cwd",
        default=None,
        metavar="DIR",
        help=(
            "EDA run directory for -F filelists and relative paths "
            "(default: parent of top .f, or env HCH_INDEX_CWD). "
            "Filelist tokens like $REPO/a.v expand from the shell environment."
        ),
    )
    io.add_argument(
        "--export-json",
        metavar="PATH",
        help="Write DQL-ready instances JSON after indexing",
    )
    io.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress messages on stderr",
    )

    roots = ap.add_argument_group("hierarchy roots & depth")
    roots.add_argument(
        "--top",
        default=None,
        help="Top module name for hierarchy flatten (root instance path)",
    )
    roots.add_argument(
        "--tops",
        default=None,
        help="Comma-separated top modules (overrides single --top flatten roots)",
    )
    roots.add_argument(
        "--max-depth",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Limit parse + hierarchy to N instance levels below --top "
            "(0=top only, 1=top+children; requires --top)"
        ),
    )
    roots.add_argument(
        "--depth-anchor",
        action="append",
        default=[],
        metavar="GLOB",
        help=(
            "Legacy anchor glob: instance name, module type, or RTL file stem "
            "(repeatable). Prefer --depth-anchor-inst / --depth-anchor-module."
        ),
    )
    roots.add_argument(
        "--depth-anchor-inst",
        action="append",
        default=[],
        metavar="GLOB",
        help="Anchor on instance leaf name only (repeatable), e.g. 'u_*_top'",
    )
    roots.add_argument(
        "--depth-anchor-module",
        action="append",
        default=[],
        metavar="GLOB",
        help="Anchor on module type name only (repeatable), e.g. '*_top*'",
    )
    roots.add_argument(
        "--depth-shallow",
        type=int,
        default=2,
        metavar="N",
        help="Descendant levels to parse when path matches no --depth-anchor (default: 2)",
    )
    roots.add_argument(
        "--depth-anchor-extra",
        type=int,
        default=None,
        metavar="N",
        help=(
            "With --depth-anchor: parse only N instance levels below each anchor match "
            "(e.g. '*_top*' + 2 → two levels under every *_top* node). "
            "Default: full depth below anchors (capped by --max-depth if set)"
        ),
    )
    roots.add_argument(
        "--no-skim-parse",
        action="store_true",
        help=(
            "With --depth-anchor: parse shallow-zone files with pyslang too "
            "(default: text-skim for shallow, pyslang only on anchor branches)"
        ),
    )
    roots.add_argument(
        "--path-hierarchy",
        choices=("auto", "on", "off"),
        default="auto",
        help="Synthetic u_* path layout: auto (detect), on, or off",
    )

    bb = ap.add_argument_group(
        "IP / kit blackbox",
        "Skip full pyslang parse on vendor IP paths (module header scan → blackbox stub). "
        "Parent instances still indexed. Also env HCH_BLACKBOX_PATH=comma,separated",
    )
    bb.add_argument(
        "--blackbox-path",
        action="append",
        default=[],
        metavar="SUBSTR",
        help=(
            "RTL path substring to blackbox (repeatable; matched on resolved file paths). "
            "Merged with HCH_BLACKBOX_PATH"
        ),
    )

    perf = ap.add_argument_group("performance & checkpoint")
    perf.add_argument(
        "--batch-size",
        type=int,
        default=0,
        help="Sources per pyslang batch (0=all at once). Enables checkpoint when >0",
    )
    perf.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=0,
        help="Parallel parse workers for batched Tier P (0=auto CPU count, 1=sequential)",
    )
    perf.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Resume from checkpoint_files in existing DB",
    )
    perf.add_argument(
        "--force",
        action="store_true",
        help="Ignore checkpoint and rebuild module/instance tables",
    )

    tier_e = ap.add_argument_group("Tier E elaboration")
    tier_e.add_argument(
        "--elaborate",
        action="store_true",
        help="Tier E: use pyslang elaboration (generate/ifdef resolved)",
    )
    tier_e.add_argument(
        "--elab-instance-cap",
        type=int,
        default=50_000,
        help="Max elaborated instances (Tier E); meta when truncated",
    )
    tier_e.add_argument(
        "--no-elab-fast",
        action="store_true",
        help="Tier E: parse full filelist for ingest (disable closure-fast path)",
    )
    tier_e.add_argument(
        "--elab-deep",
        choices=("auto", "hybrid", "shallow", "closure"),
        default="auto",
        help="Deep synthetic: auto=path+shallow slang hybrid, shallow=8-file only, closure=pruned slang only",
    )

    diag = ap.add_argument_group("variants & diagnostics")
    diag.add_argument(
        "--ifdef-compare",
        action="store_true",
        help="Compare instance sets: filelist defines vs --ifdef-alt",
    )
    diag.add_argument(
        "--ifdef-alt",
        default="",
        help="Extra defines for ifdef compare, e.g. USE_ALT=1,FOO=2",
    )
    diag.add_argument(
        "--filelist-diff",
        metavar="OTHER.f",
        default=None,
        help="Compare primary filelist with another; store filelist_diff_json meta",
    )
    diag.add_argument(
        "--variant",
        action="append",
        default=[],
        help="Preprocessor variant NAME=DEFINE,... (repeatable); indexes into one DB",
    )
    diag.add_argument(
        "--variant-compare",
        metavar="A,B",
        default=None,
        help="After --variant indexing, diff instance paths between variants A and B",
    )
    diag.add_argument(
        "--variant-dir",
        metavar="DIR",
        default=None,
        help="With --variant: also write one .hch.db per variant under DIR (ifdef multi-DB)",
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

    reporter: IndexProgressReporter | None = None
    on_progress = None
    on_phase = None
    if not args.quiet:
        reporter = IndexProgressReporter()
        on_progress = reporter.files
        on_phase = reporter.phase
        reporter.phase(f"Output: {args.output}")

    with progress_stderr_guard(reporter):
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
            on_progress=on_progress,
            on_phase=on_phase,
            index_cwd=index_cwd,
            jobs=args.jobs,
            blackbox_paths=args.blackbox_path,
            max_depth=args.max_depth,
            depth_anchor_patterns=args.depth_anchor,
            depth_anchor_inst_patterns=args.depth_anchor_inst,
            depth_anchor_module_patterns=args.depth_anchor_module,
            depth_shallow=args.depth_shallow,
            depth_anchor_extra=args.depth_anchor_extra,
            skim_parse=not args.no_skim_parse,
        )
    n = store.count_instances()
    m = store.count_modules()
    if reporter:
        for key, val in reporter.meta().items():
            store.set_meta(key, val)
        store.conn.commit()
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
    if reporter:
        print(reporter.summary(instances=n, db_path=args.output, modules=m))
    else:
        print(f"Indexed {n} instances -> {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())