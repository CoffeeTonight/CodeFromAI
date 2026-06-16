"""Execute one scan-inst run from a resolved RunConfig."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Optional

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
from scan_inst.hierarchy_log import emit_hierarchy_rows_log, emit_path_provenance_log, rows_lookup
from scan_inst.report import RunReport, default_log_path, emit_run_report
from scan_inst.path_chain import attach_path_chains, format_path_chain_compact
from scan_inst.path_search import search_hierarchy_path
from scan_inst.connect_request import ConnectivityCheck, ConnectivityRequest
from scan_inst.connectivity import (
    check_connectivity,
    emit_connect_trace_log,
    format_connect_results_tsv,
    print_connect_trace_reports,
    run_connectivity_request,
)
from scan_inst.path_walk import run_path_walk_connect, run_path_walk_index
from scan_inst.run_request import (
    normalize_run_mode,
    resolve_connectivity_request,
    resolve_effective_run_mode,
)
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
from scan_inst.search import normalize_search_patterns, search
from scan_inst.top_find import find_top_modules, resolve_top_modules
from scan_inst.run_request import RunConfig


def execute_run(cfg: RunConfig, ap) -> int:
    connect_request: Optional[ConnectivityRequest] = None
    if cfg.check_connect_batch or cfg.connect_inline:
        connect_request = resolve_connectivity_request(cfg)

    effective_mode = resolve_effective_run_mode(cfg, connect_request)
    index_strategy = normalize_run_mode(cfg.index_strategy or "full-index")
    path_walk_mode = effective_mode == "path-walk" or index_strategy == "path-walk"
    cone_mode = effective_mode == "cone"
    inst_trace_mode = effective_mode == "inst-trace"
    connect_run_mode = effective_mode in (
        "check-connect",
        "check-connect-batch",
        "path-walk",
    )
    if cfg.check_connect and connect_request is not None:
        ap.error("use either check_connect or check_connect_batch/connect, not both")
    if cfg.fanin_cone and cfg.fanout_cone:
        ap.error("use either fanin_cone or fanout_cone, not both")
    if path_walk_mode and connect_run_mode and connect_request is None:
        ap.error("path-walk connect requires checks in batch JSON or --check-connect")
    if effective_mode == "check-connect-batch" and connect_request is None:
        ap.error(
            "check-connect-batch mode requires checks/pairs in batch JSON "
            "or a pairs text file"
        )
    if inst_trace_mode and cfg.inst_trace is None:
        ap.error("inst-trace mode requires inst_trace in JSON")
    if cone_mode and not (cfg.fanin_cone or cfg.fanout_cone):
        ap.error("cone mode requires fanin_cone or fanout_cone in JSON")

    t0 = time.perf_counter()
    extra_defines = dict(cfg.defines_map)
    if connect_request is not None:
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

    lazy = lazy_processing_enabled()
    if lazy and on_progress:
        ifdef_note = "ifdef at index" if lazy_index_ifdef() else "ifdef/macro deferred"
        on_progress(
            f"index: lazy ({ifdef_note}; connect/elab on-demand; "
            f"SCAN_INST_LAZY=0 to disable)"
        )

    fl = parse_filelist(
        cfg.filelist,
        index_cwd=cfg.index_cwd,
        extra_defines=extra_defines,
        on_progress=on_progress,
        ignore_filelists=list(cfg.ignore_filelist),
        defer_source_exists=lazy_filelist_defer_exists(),
    )
    if not fl.source_files:
        print("No sources in filelist", file=sys.stderr)
        return 1

    if path_walk_mode:
        if on_progress:
            on_progress("path-walk: on-demand index (endpoint paths only)")
        top_for_walk = (
            cfg.top
            or (connect_request.top if connect_request else "")
            or (cfg.inst_trace.top if cfg.inst_trace else "")
            or (fl.top_modules[0] if fl.top_modules else "")
        )
        if not top_for_walk:
            print("path-walk requires --top or JSON top", file=sys.stderr)
            return 2
        pw_ignore = dict(
            ignore_paths=list(cfg.ignore_path),
            ignore_path_files=list(cfg.ignore_path_file),
            ignore_modules=list(cfg.ignore_module),
            ignore_filelists=list(cfg.ignore_filelist),
            on_progress=on_progress,
        )
        elapsed = time.perf_counter() - t0

        if inst_trace_mode:
            assert cfg.inst_trace is not None
            try:
                index, pw_state, top_name = run_path_walk_index(
                    fl,
                    [cfg.inst_trace.instance],
                    top=top_for_walk,
                    extra_defines=extra_defines,
                    **pw_ignore,
                )
            except ValueError as exc:
                print(str(exc), file=sys.stderr)
                return 2
            trace_result = run_inst_trace(
                cfg.inst_trace,
                rows=pw_state.rows(),
                index=index,
                top=top_name,
                defines=extra_defines,
            )
            if not cfg.quiet:
                emit_path_provenance_log(
                    trace_result.instance,
                    rows_lookup(pw_state.rows()),
                    stream=sys.stderr,
                    label="instance",
                    prefix="[scan-inst inst-trace]",
                )
            trace_rows = rows_lookup(pw_state.rows())
            term_stream = sys.stderr if cfg.output == "-" else sys.stdout
            print_inst_trace_report(
                trace_result,
                stream=term_stream,
                rows_by_path=trace_rows,
            )
            if log_path is not None:
                with open(log_path, "a", encoding="utf-8") as fh:
                    print_inst_trace_report(
                        trace_result,
                        stream=fh,
                        rows_by_path=trace_rows,
                    )
            body = format_inst_trace_tsv(trace_result)
            report_mode = "inst-trace"
            search_pattern = cfg.inst_trace.instance
        elif cone_mode:
            cone_label = cfg.fanout_cone or cfg.fanin_cone or ""
            try:
                index, pw_state, top_name = run_path_walk_index(
                    fl,
                    [cone_label],
                    top=top_for_walk,
                    extra_defines=extra_defines,
                    **pw_ignore,
                )
            except ValueError as exc:
                print(str(exc), file=sys.stderr)
                return 2
            over_approx = (
                cfg.over_approximate_if
                if cfg.over_approximate_if is not None
                else True
            )
            if cfg.fanout_cone:
                cone_result = fanout_cone(
                    cfg.fanout_cone,
                    rows=pw_state.rows(),
                    index=index,
                    top=top_name,
                    defines=extra_defines,
                    over_approximate_if=over_approx,
                )
                report_mode = "fanout-cone"
            else:
                assert cfg.fanin_cone is not None
                cone_result = fanin_cone(
                    cfg.fanin_cone,
                    rows=pw_state.rows(),
                    index=index,
                    top=top_name,
                    defines=extra_defines,
                    over_approximate_if=over_approx,
                )
                report_mode = "fanin-cone"
            if not cfg.quiet:
                emit_path_provenance_log(
                    cone_result.origin_scope,
                    rows_lookup(pw_state.rows()),
                    stream=sys.stderr,
                    label="origin",
                    prefix="[scan-inst cone]",
                )
            cone_rows = rows_lookup(pw_state.rows())
            term_stream = sys.stderr if cfg.output == "-" else sys.stdout
            print_cone_report(
                cone_result,
                stream=term_stream,
                rows_by_path=cone_rows,
            )
            if log_path is not None:
                with open(log_path, "a", encoding="utf-8") as fh:
                    print_cone_report(
                        cone_result,
                        stream=fh,
                        rows_by_path=cone_rows,
                    )
            if cfg.cone_graph:
                write_cone_dot(cone_result, cfg.cone_graph)
            body = format_cone_tsv(cone_result)
            search_pattern = cone_label
        else:
            if cfg.check_connect and connect_request is None:
                connect_request = ConnectivityRequest(
                    checks=(
                        ConnectivityCheck(
                            cfg.check_connect[0],
                            cfg.check_connect[1],
                        ),
                    ),
                    top=cfg.top or "",
                )
                extra_defines.update(connect_request.defines)
            else:
                connect_request = resolve_connectivity_request(cfg)
                if connect_request is None:
                    print("missing connectivity request", file=sys.stderr)
                    return 1
                extra_defines.update(connect_request.defines)
            try:
                batch, index, pw_state = run_path_walk_connect(
                    connect_request,
                    fl,
                    top=top_for_walk,
                    extra_defines=extra_defines,
                    **pw_ignore,
                )
            except ValueError as exc:
                print(str(exc), file=sys.stderr)
                return 2
            connect_results = batch.results
            body = format_connect_results_tsv(
                connect_results,
                modules_cached=batch.modules_cached,
            )
            endpoint_rows = pw_state.rows_by_path
            if not cfg.quiet:
                for result in connect_results:
                    emit_connect_trace_log(
                        result,
                        stream=sys.stderr,
                        check_prefix=result.check_id or "",
                        rows_by_path=endpoint_rows,
                    )
            use_trace = cfg.connect_trace or cfg.connect_log
            if connect_request.trace or use_trace:
                term_stream = sys.stderr if cfg.output == "-" else sys.stdout
                print_connect_trace_reports(
                    connect_results,
                    stream=term_stream,
                    rows_by_path=endpoint_rows,
                )
            if on_progress and not cfg.quiet:
                on_progress(
                    f"path-walk: done {pw_state.stats.checks_run} check(s), "
                    f"{len(pw_state.rows_by_path)} row(s), "
                    f"{pw_state.stats.modules_loaded} module(s), "
                    f"{time.perf_counter() - t0:.1f}s"
                )
            emit_run_report(
                RunReport(
                    filelist_path=cfg.filelist,
                    elapsed_sec=time.perf_counter() - t0,
                    fl=fl,
                    index=index,
                    cache_enabled=False,
                    elab_tops=[top_for_walk],
                    instance_rows=len(pw_state.rows_by_path),
                    mode="path-walk",
                    output_path=cfg.output,
                    filelist_warnings=len(fl.errors),
                ),
                log_path=log_path,
            )
            return 0

        if cfg.output == "-":
            sys.stdout.write(body)
        else:
            with open(cfg.output, "w", encoding="utf-8") as f:
                f.write(body)
        if on_progress and not cfg.quiet:
            on_progress(
                f"path-walk: done 1 trace step, "
                f"{len(pw_state.rows_by_path)} row(s), "
                f"{pw_state.stats.modules_loaded} module(s), "
                f"{time.perf_counter() - t0:.1f}s"
            )
        emit_run_report(
            RunReport(
                filelist_path=cfg.filelist,
                elapsed_sec=time.perf_counter() - t0,
                fl=fl,
                index=index,
                cache_enabled=False,
                elab_tops=[top_name],
                instance_rows=len(pw_state.rows_by_path),
                mode=report_mode,
                output_path=cfg.output,
                filelist_warnings=len(fl.errors),
                search_pattern=search_pattern,
            ),
            log_path=log_path,
        )
        return 0

    heartbeat = ProgressHeartbeat(
        reporter.phase,
        "index",
        enabled=not cfg.quiet and len(fl.source_files) >= 500,
        get_detail=reporter.get_detail,
    )
    low_memory = effective_low_memory(
        explicit=cfg.low_memory,
        num_sources=len(fl.source_files),
    )
    if low_memory and not cfg.low_memory and on_progress:
        on_progress(
            f"index: auto low-memory fused build ({len(fl.source_files)} sources)"
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
            ignore_filelists=list(cfg.ignore_filelist),
            jobs=cfg.jobs,
            use_cache=use_cache,
            refresh_cache=cfg.refresh_cache,
            low_memory=low_memory,
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

    elab_scope = None
    use_scoped_elab = (
        lazy_scoped_connect_elab()
        and connect_run_mode
        and not cone_mode
        and not inst_trace_mode
    )
    if use_scoped_elab:
        pair = tuple(cfg.check_connect) if cfg.check_connect else None
        specs = endpoint_specs_from_request(connect_request, pair=pair)
        if specs:
            top_for_scope = tops[0] if tops else ""
            elab_scope = elab_scope_paths(specs, top=top_for_scope)
            if on_progress:
                on_progress(f"elab: scoped {len(elab_scope)} path(s) for connect")

    def _get_cached_elab(top_name: str):
        if not use_cache or elab_scope is not None:
            return None
        return get_cached_elab(bundle, top_name, cfg.max_depth)

    def _store_cached_elab(
        top_name: str,
        root,
        part,
    ) -> None:
        if elab_scope is not None:
            return
        store_cached_elab(
            bundle,
            top_name,
            cfg.max_depth,
            root,
            part,
            cache_dir=cache_dir,
            use_cache=use_cache,
        )

    roots, rows, elab_cache_hits = elaborate_tops_parallel(
        index,
        tops,
        max_depth=cfg.max_depth,
        scope_paths=elab_scope,
        jobs=cfg.jobs,
        get_cached=_get_cached_elab,
        store_cached=_store_cached_elab,
        on_progress=on_progress,
    )
    if elab_cache_hits and on_progress:
        on_progress(f"cache hit: elab ({elab_cache_hits}/{len(tops)} tops)")
    rows.sort(key=lambda r: (r.full_path.count("."), r.full_path))
    elapsed = time.perf_counter() - t0
    coverage = (
        compute_coverage_audit(index, fl, rows, tops=tops) if rows and tops else None
    )
    if not cfg.quiet and effective_mode == "hierarchy" and rows:
        emit_hierarchy_rows_log(rows, stream=sys.stderr)

    if inst_trace_mode:
        assert cfg.inst_trace is not None
        top_name = (
            cfg.inst_trace.top
            or cfg.top
            or (tops[0] if tops else "")
        )
        compile_defines = dict(fl.defines)
        compile_defines.update(extra_defines)
        trace_result = run_inst_trace(
            cfg.inst_trace,
            rows=rows,
            index=index,
            top=top_name,
            defines=compile_defines,
        )
        if not cfg.quiet:
            emit_path_provenance_log(
                trace_result.instance,
                rows_lookup(rows),
                stream=sys.stderr,
                label="instance",
                prefix="[scan-inst inst-trace]",
            )
        trace_rows = rows_lookup(rows)
        term_stream = sys.stderr if cfg.output == "-" else sys.stdout
        print_inst_trace_report(
            trace_result,
            stream=term_stream,
            rows_by_path=trace_rows,
        )
        if log_path is not None:
            with open(log_path, "a", encoding="utf-8") as fh:
                print_inst_trace_report(
                    trace_result,
                    stream=fh,
                    rows_by_path=trace_rows,
                )
        body = format_inst_trace_tsv(trace_result)
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
                mode="inst-trace",
                output_path=cfg.output,
                filelist_warnings=len(fl.errors),
                search_pattern=cfg.inst_trace.instance,
                coverage=coverage,
            ),
            log_path=log_path,
        )
    elif cone_mode:
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
        if not cfg.quiet:
            emit_path_provenance_log(
                cone_result.origin_scope,
                rows_lookup(rows),
                stream=sys.stderr,
                label="origin",
                prefix="[scan-inst cone]",
            )
        cone_rows = rows_lookup(rows)
        term_stream = sys.stderr if cfg.output == "-" else sys.stdout
        print_cone_report(
            cone_result,
            stream=term_stream,
            rows_by_path=cone_rows,
        )
        if log_path is not None:
            with open(log_path, "a", encoding="utf-8") as fh:
                print_cone_report(
                    cone_result,
                    stream=fh,
                    rows_by_path=cone_rows,
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
    elif connect_run_mode:
        top_name = tops[0] if tops else ""
        compile_defines = dict(fl.defines)
        compile_defines.update(extra_defines)
        use_trace = cfg.connect_trace or cfg.connect_log
        if effective_mode in ("check-connect-batch", "path-walk"):
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
                jobs=cfg.jobs,
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
        if not cfg.quiet:
            endpoint_rows = rows_lookup(rows)
            for result in connect_results:
                emit_connect_trace_log(
                    result,
                    stream=sys.stderr,
                    check_prefix=result.check_id or "",
                    rows_by_path=endpoint_rows,
                )
        if use_trace:
            term_stream = sys.stderr if cfg.output == "-" else sys.stdout
            print_connect_trace_reports(
                connect_results,
                stream=term_stream,
                rows_by_path=endpoint_rows,
            )
            if log_path is not None:
                with open(log_path, "a", encoding="utf-8") as fh:
                    print_connect_trace_reports(
                        connect_results,
                        stream=fh,
                        title="connectivity path evidence (log)",
                        rows_by_path=endpoint_rows,
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
                mode=effective_mode,
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
                hierarchy_rows=rows,
            ),
            log_path=log_path,
        )


