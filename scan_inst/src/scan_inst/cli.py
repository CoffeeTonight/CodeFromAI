"""scan-inst CLI."""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Optional

import os

import scan_inst
from scan_inst.coverage_audit import compute_coverage_audit
from scan_inst.cache import (
    default_cache_dir,
    get_cached_elab,
    load_or_build_index,
    store_cached_elab,
)
from scan_inst.elab import elaborate
from scan_inst.filelist import parse_filelist
from scan_inst.progress import ProgressHeartbeat, ProgressReporter, progress_callback
from scan_inst.report import RunReport, default_log_path, emit_run_report
from scan_inst.path_chain import attach_path_chains, format_path_chain_compact
from scan_inst.path_search import search_hierarchy_path
from scan_inst.connect_request import ConnectivityRequest
from scan_inst.connectivity import (
    check_connectivity,
    format_connect_results_tsv,
    print_connect_trace_reports,
    run_connectivity_request,
)
from scan_inst.run_request import (
    jobs_from_env,
    jobs_hint_from_config_text,
    load_run_request_with_jobs_source,
    merge_options_from_connect_batch_json,
    merge_run_config,
    resolve_connectivity_request,
    resolve_jobs_after_merge,
    run_config_from_args,
    try_load_run_request_from_path,
)
from scan_inst.cone import (
    fanin_cone,
    fanout_cone,
    format_cone_tsv,
    print_cone_report,
    write_cone_dot,
)
from scan_inst.help_text import (
    CONE_HELP,
    CONNECT_HELP,
    CONFIG_HELP,
    HELP_DESCRIPTION,
    HELP_EPILOG,
    STRESS_HELP,
)
from scan_inst.search import normalize_search_patterns, search
from scan_inst.top_find import find_top_modules, resolve_top_modules


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
        metavar="FILELIST.f",
        help="top Verilog filelist; optional with --config (see also JSON field filelist)",
    )

    cfg = ap.add_argument_group("config")
    cfg.add_argument(
        "-c",
        "--config",
        default=None,
        metavar="RUN.json",
        help="run spec JSON: filelist, mode, search/connect, cache, ignore, output",
    )
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
    if not args.config and not args.filelist:
        ap.error("filelist or --config is required")
    if args.check_connect and args.check_connect_batch:
        ap.error("use either --check-connect or --check-connect-batch, not both")
    if args.fanin_cone and args.fanout_cone:
        ap.error("use either --fanin-cone or --fanout-cone, not both")

    cli_cfg = run_config_from_args(args)
    config_path: Optional[Path] = None
    json_jobs_source: Optional[str] = None
    config_arg = args.config or os.environ.get("SCAN_INST_CONFIG")
    if config_arg:
        config_path = Path(config_arg)
        base_cfg, json_jobs_source = load_run_request_with_jobs_source(config_path)
        cfg = merge_run_config(base_cfg, cli_cfg, args)
    elif args.filelist:
        auto = try_load_run_request_from_path(args.filelist)
        if auto is not None:
            config_path, base_cfg, json_jobs_source = auto
            cfg = merge_run_config(base_cfg, cli_cfg, args)
        else:
            cfg = cli_cfg
    else:
        cfg = cli_cfg
    if not cfg.filelist:
        ap.error("filelist is required (positional or in --config JSON)")

    connect_batch_jobs_source: Optional[str] = None
    connect_batch_path: Optional[Path] = None
    if cfg.check_connect_batch:
        connect_batch_path = Path(cfg.check_connect_batch)
        cfg, connect_batch_jobs_source = merge_options_from_connect_batch_json(
            cfg,
            connect_batch_path,
            args,
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

    if not cfg.quiet:
        pkg_dir = Path(scan_inst.__file__).resolve().parent
        print(
            f"run: scan-inst {scan_inst.__version__} ({pkg_dir})",
            file=sys.stderr,
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
        else:
            print(
                f"run: no config loaded jobs={jobs_res.note} "
                f"(source={jobs_res.source}; use -c run.json, "
                f"jobs in --check-connect-batch JSON, or SCAN_INST_CONFIG)",
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

    batch_mode = bool(cfg.check_connect_batch or cfg.connect_inline)
    cone_mode = bool(cfg.fanin_cone or cfg.fanout_cone)
    if cfg.check_connect and batch_mode:
        ap.error("use either check_connect or check_connect_batch/connect, not both")
    if cone_mode and (cfg.check_connect or batch_mode or cfg.search or cfg.search_path):
        ap.error("cone mode is exclusive with search/connect modes")
    if cfg.fanin_cone and cfg.fanout_cone:
        ap.error("use either fanin_cone or fanout_cone, not both")

    t0 = time.perf_counter()
    extra_defines = dict(cfg.defines_map)
    connect_request: Optional[ConnectivityRequest] = None
    if batch_mode:
        connect_request = resolve_connectivity_request(cfg)
        if connect_request is None:
            print("missing connectivity request", file=sys.stderr)
            return 1
        extra_defines.update(connect_request.defines)
    cache_dir = default_cache_dir() if cfg.cache_dir is None else Path(cfg.cache_dir)
    use_cache = not cfg.no_cache
    reporter = ProgressReporter(enabled=not cfg.quiet)
    reporter.set_filelist(cfg.filelist)
    on_progress = progress_callback(reporter)
    log_path: Path | None = None
    if not cfg.no_log_file:
        log_path = (
            Path(cfg.log_file)
            if cfg.log_file
            else default_log_path(cfg.filelist, cfg.output)
        )

    fl = parse_filelist(
        cfg.filelist,
        index_cwd=cfg.index_cwd,
        extra_defines=extra_defines,
        on_progress=on_progress,
    )
    if not fl.source_files:
        print("No sources in filelist", file=sys.stderr)
        return 1

    heartbeat = ProgressHeartbeat(
        reporter.phase,
        "index",
        enabled=not cfg.quiet and len(fl.source_files) >= 500,
        get_detail=reporter.get_detail,
    )
    with heartbeat:
        index, bundle, index_cache_hit, index_rebuilt, index_incremental, cache_path = (
            load_or_build_index(
            cfg.filelist,
            fl,
            cache_dir=cache_dir,
            extra_defines=extra_defines,
            ignore_paths=list(cfg.ignore_path),
            ignore_path_files=list(cfg.ignore_path_file),
            ignore_modules=list(cfg.ignore_module),
            jobs=cfg.jobs,
            use_cache=use_cache,
            refresh_cache=cfg.refresh_cache,
            low_memory=cfg.low_memory,
            on_progress=on_progress,
            )
        )
    if index_cache_hit and not cfg.quiet:
        reporter.phase(f"cache hit: index ({len(index.modules)} modules)")

    if cfg.find_top:
        tops = find_top_modules(index)
        elapsed = time.perf_counter() - t0
        lines = ["module\tfile\tstop_reason"]
        for name in tops:
            rec = index.get_module(name)
            file_p = rec.file_path if rec else ""
            stop = index.module_stop_reason(name)
            lines.append(f"{name}\t{file_p}\t{stop}")
        body = "\n".join(lines) + "\n"
        if cfg.output == "-":
            sys.stdout.write(body)
        else:
            with open(cfg.output, "w", encoding="utf-8") as f:
                f.write(body)
        emit_run_report(
            RunReport(
                filelist_path=cfg.filelist,
                elapsed_sec=elapsed,
                fl=fl,
                index=index,
                cache_path=cache_path if use_cache else None,
                cache_enabled=use_cache,
                index_cache_hit=index_cache_hit,
                index_rebuilt=index_rebuilt,
                index_incremental=index_incremental,
                top_candidates=len(tops),
                mode="find-top",
                output_path=cfg.output,
                filelist_warnings=len(fl.errors),
            ),
            log_path=log_path,
        )
        return 0

    try:
        tops = resolve_top_modules(
            index,
            top=cfg.top or (connect_request.top if connect_request else ""),
            filelist_tops=fl.top_modules,
            all_tops=cfg.all_tops,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        print("Hint: scan-inst ... --find-top", file=sys.stderr)
        return 2

    rows = []
    roots = []
    elab_cache_hits = 0
    for top_name in tops:
        cached = get_cached_elab(bundle, top_name, cfg.max_depth) if use_cache else None
        if cached is not None:
            root, part = cached
            elab_cache_hits += 1
        else:
            if on_progress:
                on_progress(f"elab: elaborating top {top_name}")
            root, part = elaborate(index, top_name, max_depth=cfg.max_depth)
            store_cached_elab(
                bundle,
                top_name,
                cfg.max_depth,
                root,
                part,
                cache_dir=cache_dir,
                use_cache=use_cache,
            )
        roots.append(root)
        rows.extend(part)
    if elab_cache_hits and on_progress:
        on_progress(f"cache hit: elab ({elab_cache_hits}/{len(tops)} tops)")
    rows.sort(key=lambda r: (r.full_path.count("."), r.full_path))
    elapsed = time.perf_counter() - t0
    coverage = (
        compute_coverage_audit(index, fl, rows, tops=tops) if rows and tops else None
    )

    if cone_mode:
        top_name = tops[0] if tops else ""
        compile_defines = dict(fl.defines)
        compile_defines.update(extra_defines)
        over_approx = (
            cfg.over_approximate_if
            if cfg.over_approximate_if is not None
            else True
        )
        if cfg.fanout_cone:
            cone_result = fanout_cone(
                cfg.fanout_cone,
                rows=rows,
                index=index,
                top=top_name,
                defines=compile_defines,
                over_approximate_if=over_approx,
            )
            cone_label = cfg.fanout_cone
            mode_name = "fanout-cone"
        else:
            assert cfg.fanin_cone is not None
            cone_result = fanin_cone(
                cfg.fanin_cone,
                rows=rows,
                index=index,
                top=top_name,
                defines=compile_defines,
                over_approximate_if=over_approx,
            )
            cone_label = cfg.fanin_cone
            mode_name = "fanin-cone"
        term_stream = sys.stderr if cfg.output == "-" else sys.stdout
        print_cone_report(cone_result, stream=term_stream)
        if log_path is not None:
            with open(log_path, "a", encoding="utf-8") as fh:
                print_cone_report(
                    cone_result,
                    stream=fh,
                )
        if cfg.cone_graph:
            write_cone_dot(cone_result, cfg.cone_graph)
        body = format_cone_tsv(cone_result)
        if cfg.output == "-":
            sys.stdout.write(body)
        else:
            with open(cfg.output, "w", encoding="utf-8") as f:
                f.write(body)
        emit_run_report(
            RunReport(
                filelist_path=cfg.filelist,
                elapsed_sec=elapsed,
                fl=fl,
                index=index,
                cache_path=cache_path if use_cache else None,
                cache_enabled=use_cache,
                index_cache_hit=index_cache_hit,
                index_rebuilt=index_rebuilt,
                index_incremental=index_incremental,
                elab_tops=tops,
                elab_cache_hits=elab_cache_hits,
                instance_rows=len(rows),
                mode=mode_name,
                output_path=cfg.output,
                filelist_warnings=len(fl.errors),
                search_pattern=cone_label,
                coverage=coverage,
            ),
            log_path=log_path,
        )
    elif cfg.check_connect or batch_mode:
        top_name = tops[0] if tops else ""
        compile_defines = dict(fl.defines)
        compile_defines.update(extra_defines)
        use_trace = cfg.connect_trace or cfg.connect_log
        if batch_mode:
            request = connect_request
            assert request is not None
            trace_on = request.trace or use_trace
            log_on = request.connect_log or cfg.connect_log
            include_ff = request.include_ff or cfg.include_ff
            if (
                trace_on != request.trace
                or log_on != request.connect_log
                or include_ff != request.include_ff
            ):
                request = ConnectivityRequest(
                    checks=request.checks,
                    top=request.top,
                    defines=request.defines,
                    trace=trace_on,
                    connect_log=log_on,
                    include_ff=include_ff,
                    strict_generate=request.strict_generate,
                    over_approximate_if=request.over_approximate_if,
                )
            batch = run_connectivity_request(
                request,
                rows=rows,
                index=index,
                top=top_name,
                extra_defines=compile_defines,
            )
            connect_results = batch.results
            body = format_connect_results_tsv(
                connect_results,
                modules_cached=batch.modules_cached,
            )
        else:
            assert cfg.check_connect is not None
            result = check_connectivity(
                cfg.check_connect[0],
                cfg.check_connect[1],
                rows=rows,
                index=index,
                top=top_name,
                defines=compile_defines,
                trace=use_trace,
                ff_barrier=not cfg.include_ff,
                strict_generate=cfg.strict_generate,
                over_approximate_if=cfg.over_approximate_if,
            )
            connect_results = [result]
            body = format_connect_results_tsv(connect_results)
        if use_trace:
            term_stream = sys.stderr if cfg.output == "-" else sys.stdout
            print_connect_trace_reports(connect_results, stream=term_stream)
            if log_path is not None:
                with open(log_path, "a", encoding="utf-8") as fh:
                    print_connect_trace_reports(
                        connect_results,
                        stream=fh,
                        title="connectivity path evidence (log)",
                    )
        if cfg.output == "-":
            sys.stdout.write(body)
        else:
            with open(cfg.output, "w", encoding="utf-8") as f:
                f.write(body)
        emit_run_report(
            RunReport(
                filelist_path=cfg.filelist,
                elapsed_sec=elapsed,
                fl=fl,
                index=index,
                cache_path=cache_path if use_cache else None,
                cache_enabled=use_cache,
                index_cache_hit=index_cache_hit,
                index_rebuilt=index_rebuilt,
                index_incremental=index_incremental,
                elab_tops=tops,
                elab_cache_hits=elab_cache_hits,
                instance_rows=len(rows),
                mode=("check-connect-batch" if batch_mode else "check-connect"),
                output_path=cfg.output,
                filelist_warnings=len(fl.errors),
                coverage=coverage,
            ),
            log_path=log_path,
        )
    elif cfg.search or cfg.search_path:
        hits = []
        if cfg.search:
            hits.extend(
                search(
                    cfg.search,
                    rows=rows,
                    match_inst=True,
                    match_module=cfg.search_module,
                    include_subtree=cfg.search_subtree,
                )
            )
        if cfg.search_path:
            hits.extend(
                search_hierarchy_path(rows, cfg.search_path, index)
            )
        if cfg.search:
            need_chain = [h for h in hits if not h.path_chain]
            if need_chain:
                top_name = tops[0] if tops else ""
                attach_path_chains(
                    need_chain, index, rows, top=top_name, refine_paths=False
                )
        hits.sort(key=lambda h: h.full_path)
        lines = [
            "full_path\tmatched\tmodule\tdepth\tfile\t"
            "via_filelist\tfilelist_chain\tstop_reason\tkind\t"
            "port\tport_found\tport_line\tport_decl\tport_param_note\t"
            "path_chain"
        ]
        for h in hits:
            lines.append(
                f"{h.full_path}\t{h.matched_name}\t{h.module}\t"
                f"{h.depth}\t{h.file}\t{h.via_filelist}\t{h.filelist_chain}\t"
                f"{h.stop_reason}\t{h.match_kind}\t"
                f"{h.port_name}\t{h.port_found}\t{h.port_line}\t"
                f"{h.port_decl}\t{h.port_param_note}\t"
                f"{format_path_chain_compact(h.path_chain)}"
            )
        body = "\n".join(lines) + "\n"
        if cfg.output == "-":
            sys.stdout.write(body)
        else:
            with open(cfg.output, "w", encoding="utf-8") as f:
                f.write(body)
        emit_run_report(
            RunReport(
                filelist_path=cfg.filelist,
                elapsed_sec=elapsed,
                fl=fl,
                index=index,
                cache_path=cache_path if use_cache else None,
                cache_enabled=use_cache,
                index_cache_hit=index_cache_hit,
                index_rebuilt=index_rebuilt,
                index_incremental=index_incremental,
                elab_tops=tops,
                elab_cache_hits=elab_cache_hits,
                instance_rows=len(rows),
                search_hits=len(hits),
                search_pattern=cfg.search_path
                or ",".join(normalize_search_patterns(cfg.search or "")),
                search_hit_details=hits,
                mode="search",
                output_path=cfg.output,
                filelist_warnings=len(fl.errors),
                coverage=coverage,
            ),
            log_path=log_path,
        )
    else:
        lines = [
            "full_path\tinst_leaf\tmodule\tdepth\tfile\t"
            "stop_reason\tvia_filelist\tfilelist_chain"
        ]
        for r in rows:
            lines.append(
                f"{r.full_path}\t{r.inst_leaf}\t{r.module}\t"
                f"{r.depth}\t{r.file}\t{r.stop_reason}\t"
                f"{r.via_filelist}\t{r.filelist_chain}"
            )
        body = "\n".join(lines) + "\n"
        if cfg.output == "-":
            sys.stdout.write(body)
        else:
            with open(cfg.output, "w", encoding="utf-8") as f:
                f.write(body)
        emit_run_report(
            RunReport(
                filelist_path=cfg.filelist,
                elapsed_sec=elapsed,
                fl=fl,
                index=index,
                cache_path=cache_path if use_cache else None,
                cache_enabled=use_cache,
                index_cache_hit=index_cache_hit,
                index_rebuilt=index_rebuilt,
                index_incremental=index_incremental,
                elab_tops=tops,
                elab_cache_hits=elab_cache_hits,
                instance_rows=len(rows),
                mode="hierarchy",
                output_path=cfg.output,
                filelist_warnings=len(fl.errors),
                coverage=coverage,
            ),
            log_path=log_path,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())