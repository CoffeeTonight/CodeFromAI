"""scan-inst CLI."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Mapping, Optional

import os

import scan_inst
from scan_inst.coverage_audit import compute_coverage_audit
from scan_inst.cache import (
    default_cache_dir,
    get_cached_elab,
    load_or_build_index,
    store_cached_elab,
)
from scan_inst.elab import elaborate_tops_parallel
from scan_inst.lazy_scope import (
    elab_scope_paths,
    endpoint_specs_from_request,
    lazy_filelist_defer_exists,
    lazy_index_ifdef,
    lazy_processing_enabled,
    lazy_scoped_connect_elab,
)
from scan_inst.perf import effective_low_memory
from scan_inst.filelist import parse_filelist
from scan_inst.progress import ProgressHeartbeat, ProgressReporter, progress_callback
from scan_inst.report import RunReport, default_log_path, emit_run_report
from scan_inst.path_chain import attach_path_chains, format_path_chain_compact
from scan_inst.path_search import search_hierarchy_path
from scan_inst.connect_request import ConnectivityCheck, ConnectivityRequest
from scan_inst.connectivity import (
    check_connectivity,
    format_connect_results_tsv,
    print_connect_trace_reports,
    run_connectivity_request,
)
from scan_inst.path_walk import run_path_walk_connect
from scan_inst.enable_diagnostics import (
    audit_run_on_full_index_enable_lines,
    find_nested_full_index_blocks,
    format_enable_root_cause_hint,
    resolve_block_enabled,
)
from scan_inst.run_request import (
    RUN_ON_FULL_INDEX,
    RunConfig,
    _full_index_block_key,
    _jobs_from_document,
    _mapping_get_ci,
    apply_config_env_from_document,
    is_run_test_suite_document,
    jobs_from_env,
    jobs_hint_from_config_text,
    load_run_request_with_jobs_source,
    loads_json_document,
    merge_options_from_connect_batch_json,
    merge_run_config,
    normalize_run_mode,
    resolve_connectivity_request,
    resolve_effective_run_mode,
    resolve_jobs_after_merge,
    run_config_from_args,
    try_load_run_request_from_path,
)
from scan_inst.startup import emit_startup_banner
from scan_inst.run_tests import (
    RunTestEntry,
    RunTestSuite,
    build_test_run_configs,
    detect_enable_key_typos,
    format_suite_enable_trace,
    list_disabled_suite_blocks,
    spec_for_test_entry,
    try_parse_run_test_suite,
)
from scan_inst.cli_execute import execute_run
from scan_inst.config_env_audit import emit_config_env_audit
from scan_inst.cone import (
    fanin_cone,
    fanout_cone,
    format_cone_tsv,
    print_cone_report,
    write_cone_dot,
)
from scan_inst.inst_trace import (
    format_inst_trace_tsv,
    print_inst_trace_report,
    run_inst_trace,
)
from scan_inst.help_text import (
    CONE_HELP,
    CONNECT_HELP,
    CONFIG_HELP,
    HELP_DESCRIPTION,
    HELP_EPILOG,
    INST_TRACE_HELP,
    STRESS_HELP,
)
from scan_inst.search import normalize_search_patterns, search
from scan_inst.top_find import find_top_modules, resolve_top_modules


def _bootstrap_flat_suite_config(
    config_path: Path,
    *,
    quiet: bool,
) -> tuple[
    Optional[dict],
    Optional[str],
    Optional[RunTestSuite],
    list[tuple[RunTestEntry, RunConfig]],
    RunConfig,
    Optional[str],
    list[str],
    list[str],
]:
    """
    Read run JSON, apply enable gate, build flat-suite test_plan.

    Must run for every run JSON path (positional RUN.json or SCAN_INST_CONFIG).
    """
    try:
        config_text = config_path.read_text(encoding="utf-8-sig")
    except OSError:
        base_cfg, jobs_src = load_run_request_with_jobs_source(config_path)
        return None, None, None, [], base_cfg, jobs_src, [], []

    json_audit: list[str] = []
    try:
        raw_doc = loads_json_document(config_text, audit=json_audit)
    except (json.JSONDecodeError, UnicodeDecodeError):
        base_cfg, jobs_src = load_run_request_with_jobs_source(config_path)
        return None, config_text, None, [], base_cfg, jobs_src, json_audit, []

    if not isinstance(raw_doc, dict):
        base_cfg, jobs_src = load_run_request_with_jobs_source(config_path)
        return None, config_text, None, [], base_cfg, jobs_src, json_audit, []

    json_env_applied = apply_config_env_from_document(raw_doc)
    if not quiet:
        pkg_dir = str(Path(scan_inst.__file__).resolve().parent)
        emit_startup_banner(
            version=scan_inst.__version__,
            pkg_dir=pkg_dir,
            stream=sys.stderr,
        )
        for line in audit_run_on_full_index_enable_lines(
            raw_doc,
            raw_text=config_text,
        ):
            print(f"run: {line}", file=sys.stderr)
        for note in json_audit:
            print(f"run: WARNING {note}", file=sys.stderr)

    parsed_suite = try_parse_run_test_suite(
        raw_doc,
        base_dir=config_path.parent,
        raw_text=config_text,
    )
    if parsed_suite is not None:
        test_plan = list(
            build_test_run_configs(
                parsed_suite,
                raw_doc,
                base_dir=config_path.parent,
            )
        )
        _, jobs_src = _jobs_from_document(raw_doc)
        return (
            raw_doc,
            config_text,
            parsed_suite,
            test_plan,
            parsed_suite.shared,
            jobs_src,
            json_audit,
            json_env_applied,
        )

    base_cfg, jobs_src = load_run_request_with_jobs_source(config_path)
    return raw_doc, config_text, None, [], base_cfg, jobs_src, json_audit, json_env_applied


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="scan-inst",
        description=HELP_DESCRIPTION,
        epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=True,
    )
    ap.add_argument(
        "filelist",
        nargs="?",
        default=None,
        metavar="FILELIST.f|RUN.json",
        help="Verilog FILELIST.f, or run-spec RUN.json (auto-detected); or set SCAN_INST_CONFIG",
    )

    cfg = ap.add_argument_group("config")
    cfg.add_argument(
        "--help-config",
        action="store_true",
        help="print run JSON field reference and examples; exit",
    )
    cfg.add_argument(
        "--help-connect",
        action="store_true",
        help="print connectivity batch JSON reference; exit",
    )
    cfg.add_argument(
        "--help-stress",
        action="store_true",
        help="print random connectivity stress / pytest commands; exit",
    )
    cfg.add_argument(
        "--help-cone",
        action="store_true",
        help="print fanin/fanout cone mode reference; exit",
    )
    cfg.add_argument(
        "--help-inst-trace",
        action="store_true",
        help="print inst-trace mode reference; exit",
    )

    elab = ap.add_argument_group("elaboration")
    elab.add_argument(
        "--top",
        default=None,
        metavar="MODULE",
        help="top module; omit with --find-top or when exactly one candidate exists",
    )
    elab.add_argument(
        "--find-top",
        action="store_true",
        help="list top-module candidates (ignorePath excluded) and exit",
    )
    elab.add_argument(
        "--all-tops",
        action="store_true",
        help="elaborate every top candidate (with or without --top)",
    )
    elab.add_argument(
        "--index-cwd",
        default=None,
        metavar="DIR",
        help="EDA cwd for -F nested filelists (env: HCH_INDEX_CWD)",
    )
    elab.add_argument(
        "--define",
        action="append",
        default=[],
        metavar="MACRO[=VAL]",
        help="extra +define for preprocess/index (repeatable; JSON: defines)",
    )
    elab.add_argument(
        "--max-depth",
        type=int,
        default=None,
        metavar="N",
        help="cap instance elaboration depth",
    )
    elab.add_argument(
        "--mode",
        default=None,
        metavar="MODE",
        help="run mode: hierarchy, path-walk, check-connect-batch, … (JSON: mode)",
    )

    out = ap.add_argument_group("output")
    out.add_argument(
        "-o",
        "--output",
        default="-",
        metavar="TSV",
        help="output TSV path (default: stdout)",
    )
    out.add_argument(
        "--quiet",
        action="store_true",
        help="suppress progress on stderr",
    )
    out.add_argument(
        "--log-file",
        default=None,
        metavar="PATH",
        help="append run report here (default: <output>.scan-inst.log)",
    )
    out.add_argument(
        "--no-log-file",
        action="store_true",
        help="do not write run report log",
    )

    srch = ap.add_argument_group("search mode")
    srch.add_argument(
        "--search",
        default=None,
        metavar="PATTERN",
        help=(
            "search instance names (globs * ?; dotted segment patterns; "
            "comma-separated: niu,sramc)"
        ),
    )
    srch.add_argument(
        "--search-subtree",
        action="store_true",
        help="with --search, include all instances under matched hierarchies",
    )
    srch.add_argument(
        "--search-path",
        default=None,
        metavar="GLOB",
        help="search hierarchy paths (e.g. top.u_*.*.clk); verify leaf port in RTL",
    )
    srch.add_argument(
        "--search-module",
        action="store_true",
        help="with --search, also match module type names",
    )

    conn = ap.add_argument_group("connectivity mode")
    conn.add_argument(
        "--check-connect",
        nargs=2,
        metavar=("A", "B"),
        help="single connectivity check: hier or hier.port endpoints",
    )
    conn.add_argument(
        "--check-connect-batch",
        metavar="FILE",
        help=(
            "batch connectivity from JSON or text pairs file "
            "(see --help-connect)"
        ),
    )
    conn.add_argument(
        "--connect-trace",
        action="store_true",
        help=(
            "record path evidence in TSV hops and print a readable path report "
            "on the terminal (stderr when -o -, else stdout)"
        ),
    )
    conn.add_argument(
        "--connect-log",
        action="store_true",
        help="same as --connect-trace; alias for JSON/scripts (implies trace)",
    )
    conn.add_argument(
        "--include-ff",
        action="store_true",
        help="connectivity: traverse always_ff D->Q (default: combinational only)",
    )

    cone = ap.add_argument_group("cone mode (COI debug)")
    cone.add_argument(
        "--fanin-cone",
        default=None,
        metavar="ENDPOINT",
        help=(
            "fanin cone from endpoint; stop at FF Q, module inputs, blackboxes "
            "(standalone; does not affect --check-connect)"
        ),
    )
    cone.add_argument(
        "--fanout-cone",
        default=None,
        metavar="ENDPOINT",
        help=(
            "fanout cone from endpoint; stop at FF D, module outputs, blackboxes "
            "(standalone; does not affect --check-connect)"
        ),
    )
    cone.add_argument(
        "--cone-graph",
        default=None,
        metavar="PATH",
        help="optional Graphviz DOT sketch of cone edges",
    )

    ign = ap.add_argument_group("ignore rules")
    ign.add_argument(
        "--ignore-path",
        action="append",
        default=[],
        metavar="PAT",
        help="RTL path glob/substring (repeatable; env: SCAN_INST_IGNORE_PATH)",
    )
    ign.add_argument(
        "--ignore-path-file",
        action="append",
        default=[],
        metavar="FILE",
        help="ignore list file (one pattern/line; module:NAME for modules)",
    )
    ign.add_argument(
        "--ignore-module",
        action="append",
        default=[],
        metavar="MOD",
        help="mark module as ignorePath (repeatable; env: SCAN_INST_IGNORE_MODULE)",
    )
    ign.add_argument(
        "--ignore-filelist",
        action="append",
        default=[],
        metavar="FL",
        help="ignore RTL listed by matching .f (repeatable; env: SCAN_INST_IGNORE_FILELIST)",
    )

    cache = ap.add_argument_group("cache and parallelism")
    cache.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=0,
        metavar="N",
        help="parallel index workers (0=auto CPU count, 1=serial)",
    )
    cache.add_argument(
        "--cache-dir",
        default=None,
        metavar="DIR",
        help="cache root (default: $SCAN_INST_CACHE_DIR or ~/.cache/scan-inst)",
    )
    cache.add_argument(
        "--no-cache",
        action="store_true",
        help="disable index/elab disk cache read and write",
    )
    cache.add_argument(
        "--refresh-cache",
        action="store_true",
        help="ignore cached index and rebuild (still writes unless --no-cache)",
    )
    cache.add_argument(
        "--low-memory",
        action="store_true",
        help="fused per-file index build (less RAM, slower cold build; default is 2-pass)",
    )
    ap.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {scan_inst.__version__} ({Path(scan_inst.__file__).resolve().parent})",
    )
    return ap


def main(argv=None) -> int:
    ap = _build_parser()
    args = ap.parse_args(argv)
    if args.help_config:
        print(CONFIG_HELP, end="" if CONFIG_HELP.endswith("\n") else "\n")
        return 0
    if args.help_connect:
        print(CONNECT_HELP, end="" if CONNECT_HELP.endswith("\n") else "\n")
        return 0
    if args.help_stress:
        print(STRESS_HELP, end="" if STRESS_HELP.endswith("\n") else "\n")
        return 0
    if args.help_cone:
        print(CONE_HELP, end="" if CONE_HELP.endswith("\n") else "\n")
        return 0
    if args.help_inst_trace:
        print(INST_TRACE_HELP, end="" if INST_TRACE_HELP.endswith("\n") else "\n")
        return 0
    run_json_arg = args.filelist or os.environ.get("SCAN_INST_CONFIG")
    if not run_json_arg and not args.check_connect_batch:
        ap.error(
            "pass RUN.json or FILELIST.f (or set SCAN_INST_CONFIG), "
            "or --check-connect-batch BATCH.json"
        )
    if args.check_connect and args.check_connect_batch:
        ap.error("use either --check-connect or --check-connect-batch, not both")
    if args.fanin_cone and args.fanout_cone:
        ap.error("use either --fanin-cone or --fanout-cone, not both")

    cli_cfg = run_config_from_args(args)
    config_path: Optional[Path] = None
    json_jobs_source: Optional[str] = None
    config_text: Optional[str] = None
    test_document: Optional[dict] = None
    test_plan: list[tuple[RunTestEntry | None, object]] = []
    saw_suite_enable_trace = False
    saw_hierarchy_execute = False
    saw_full_index_step = False
    parsed_suite = None
    json_env_applied: list[str] = []
    config_env_document: Optional[dict] = None

    cfg = cli_cfg
    if args.filelist:
        auto = try_load_run_request_from_path(args.filelist)
        if auto is not None:
            config_path, base_cfg, json_jobs_source = auto
            cfg = merge_run_config(base_cfg, cli_cfg, args)
    elif os.environ.get("SCAN_INST_CONFIG"):
        config_path = Path(os.environ["SCAN_INST_CONFIG"])

    if config_path is not None:
        (
            test_document,
            config_text,
            parsed_suite,
            suite_plan,
            base_cfg,
            json_jobs_source,
            _json_audit,
            json_env_applied,
        ) = _bootstrap_flat_suite_config(config_path, quiet=args.quiet)
        if suite_plan:
            test_plan = [(entry, run_cfg) for entry, run_cfg in suite_plan]
        cfg = merge_run_config(base_cfg, cli_cfg, args)
        config_env_document = test_document

    connect_batch_jobs_source: Optional[str] = None
    connect_batch_path: Optional[Path] = None
    if cfg.check_connect_batch:
        connect_batch_path = Path(cfg.check_connect_batch)
        (
            cfg,
            connect_batch_jobs_source,
            batch_env_applied,
            batch_document,
        ) = merge_options_from_connect_batch_json(
            cfg,
            connect_batch_path,
            args,
        )
        json_env_applied.extend(batch_env_applied)
        if config_env_document is None:
            config_env_document = batch_document

    if not cfg.filelist:
        ap.error(
            "no filelist resolved: add top-level \"filelist\" to RUN.json, "
            "pass FILELIST.f, or use --check-connect-batch JSON with filelist"
        )

    env_jobs_source: Optional[str] = None
    if cfg.jobs == 0 and int(args.jobs) == 0:
        env_jobs, env_src = jobs_from_env()
        if env_src is not None:
            cfg = replace(cfg, jobs=env_jobs)
            env_jobs_source = env_src
    jobs_res = resolve_jobs_after_merge(
        cfg,
        args,
        json_jobs_source=json_jobs_source,
        connect_batch_jobs_source=connect_batch_jobs_source,
        env_jobs_source=env_jobs_source,
    )

    if not cfg.quiet and config_env_document is not None:
        emit_config_env_audit(
            config_env_document,
            json_env_applied=json_env_applied,
            stream=sys.stderr,
        )

    if not cfg.quiet:
        if config_path is None or test_document is None:
            pkg_dir = str(Path(scan_inst.__file__).resolve().parent)
            emit_startup_banner(
                version=scan_inst.__version__,
                pkg_dir=pkg_dir,
                stream=sys.stderr,
            )
        if config_path is not None:
            print(
                f"run: config={config_path.resolve()} jobs={jobs_res.note} "
                f"(source={jobs_res.source})",
                file=sys.stderr,
            )
        elif connect_batch_path is not None:
            print(
                f"run: connect-batch={connect_batch_path.resolve()} jobs={jobs_res.note} "
                f"(source={jobs_res.source})",
                file=sys.stderr,
            )
        if cfg.mode:
            print(f"run: mode={cfg.mode}", file=sys.stderr)
        elif config_path is None and connect_batch_path is None:
            print(
                f"run: no config loaded jobs={jobs_res.note} "
                f"(source={jobs_res.source}; pass run.json, "
                f"SCAN_INST_CONFIG, or jobs in --check-connect-batch JSON)",
                file=sys.stderr,
            )
        if (
            config_path is not None
            and cfg.jobs == 0
            and json_jobs_source is None
        ):
            try:
                hint = jobs_hint_from_config_text(
                    config_path.read_text(encoding="utf-8-sig")
                )
            except OSError:
                hint = None
            if hint is not None:
                print(
                    f"run: WARNING config contains {hint!r} but jobs stayed auto; "
                    f"put {hint} at top level (not nested) or use SCAN_INST_JOBS=16",
                    file=sys.stderr,
                )

    if (
        parsed_suite is not None
        and test_plan
        and not cfg.quiet
    ):
        print(
            f"run: test-suite {len(test_plan)} step(s) from "
            f"{config_path.resolve()}",
            file=sys.stderr,
        )
        for warn in parsed_suite.enable_warnings:
            print(f"run: WARNING {warn}", file=sys.stderr)
        for typo in detect_enable_key_typos(test_document):
            print(
                f"run: WARNING unknown block {typo!r} — "
                f"enable is not read; use run_on_full_index "
                f"(or legacy run_on_full_db)",
                file=sys.stderr,
            )
        for skipped in list_disabled_suite_blocks(
            test_document,
            raw_text=config_text,
        ):
            print(
                f"run: inactive {skipped} (enable: 0; step and settings ignored)",
                file=sys.stderr,
            )
        for line in format_suite_enable_trace(
            test_document,
            parsed_suite,
            test_plan,
            raw_text=config_text,
        ):
            print(f"run: {line}", file=sys.stderr)
        saw_suite_enable_trace = True
    if not test_plan:
        if test_document is not None and is_run_test_suite_document(test_document):
            ap.error(
                "flat suite JSON has no enabled steps (all blocks enable/enabled: 0); "
                "enable at least one of run_conn_check, run_io_trace, run_cone_trace, "
                "or set run_on_full_index enable: 1"
            )
        test_plan = [(None, cfg)]

    exit_code = 0
    for test_entry, run_cfg in test_plan:
        if test_document is not None and test_entry is None:
            connect_req = resolve_connectivity_request(run_cfg)
            eff = resolve_effective_run_mode(run_cfg, connect_req)
            if eff in ("hierarchy", "search", "find-top"):
                full_key = _full_index_block_key(test_document)
                if full_key is not None:
                    spec = _mapping_get_ci(test_document, full_key)
                    if isinstance(spec, Mapping):
                        enabled, _ = resolve_block_enabled(
                            spec,
                            default=True,
                            document=test_document,
                            block_key=full_key,
                            raw_text=config_text,
                        )
                        if not enabled:
                            ap.error(
                                f"{full_key} is disabled (enable/enabled: 0) but a "
                                f"{eff} run was scheduled — JSON was not executed as a "
                                "flat suite (check block key spelling, enable vs enabled, "
                                "and that verification blocks are siblings at top level)"
                            )
                nested = find_nested_full_index_blocks(test_document)
                if nested:
                    paths = ", ".join(path for path, _ in nested)
                    ap.error(
                        f"found nested full-index block at {paths} — "
                        "run_on_full_index must be a top-level sibling of "
                        "run_conn_check / run_io_trace / run_cone_trace, not nested "
                        "under run/config/scan"
                    )
        if (
            test_document is not None
            and test_entry is not None
            and test_entry.kind == RUN_ON_FULL_INDEX
        ):
            spec = spec_for_test_entry(test_document, test_entry)
            enabled, _ = resolve_block_enabled(
                spec,
                default=True,
                document=test_document,
                block_key=RUN_ON_FULL_INDEX,
                raw_text=config_text,
            )
            if not enabled:
                ap.error(
                    "internal error: run_on_full_index scheduled despite enable/enabled: 0"
                )
        if test_entry is not None:
            if test_entry.kind == RUN_ON_FULL_INDEX:
                saw_full_index_step = True
        if test_entry is not None and not run_cfg.quiet:
            label = test_entry.name or f"{test_entry.kind}[{test_entry.index}]"
            index_note = run_cfg.index_strategy
            if (
                test_entry.kind != "run_on_full_index"
                and test_entry.mode == "full-index"
                and run_cfg.index_strategy == "path-walk"
            ):
                print(
                    f"run: note {test_entry.kind} requested full-index but "
                    f"run_on_full_index.enable is 0 — using path-walk",
                    file=sys.stderr,
                )
            print(
                f"run: test {label} kind={test_entry.kind} mode={test_entry.mode} "
                f"index={index_note} output={run_cfg.output}",
                file=sys.stderr,
            )
        step_rc = execute_run(run_cfg, ap)
        if not run_cfg.quiet:
            connect_req = resolve_connectivity_request(run_cfg)
            eff = resolve_effective_run_mode(run_cfg, connect_req)
            index_note = normalize_run_mode(run_cfg.index_strategy or "full-index")
            if eff == "hierarchy" and index_note == "full-index":
                saw_hierarchy_execute = True
        if step_rc != 0:
            exit_code = step_rc
    if not cfg.quiet:
        hint = format_enable_root_cause_hint(
            saw_suite_trace=saw_suite_enable_trace,
            saw_hierarchy_execute=saw_hierarchy_execute,
            saw_full_index_step=saw_full_index_step,
            version=scan_inst.__version__,
        )
        if hint is not None:
            print(f"run: {hint}", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())