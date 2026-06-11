"""Build SQLite index from ingested modules."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

from hch.ingest.filelist import FilelistResult, resolve_index_cwd
from hch.ingest.filelist_cache import parse_filelist_cached
from hch.ingest.filelist_config import get_last_slang_filelist_path
from hch.ingest.hierarchy_build import elaborate_flat, elaborate_flat_with_sources
from hch.ingest.ingest import get_last_parse_meta, ingest_filelist_result
from hch.index.batched_loader import build_index_batched
from hch.index.meta_contract import apply_tier_contract_meta
from hch.index.store import HierarchyStore
from hch.schema import FlatInstance, ModuleRecord

AUTO_BATCH_MIN_SOURCES = 48


def _maybe_heartbeat(
    on_phase: Optional[Callable[[str], None]],
    label: str,
):
    from hch.apps.index_progress import ProgressHeartbeat

    return ProgressHeartbeat(on_phase, label)


def _resolve_tops(
    top_module: Optional[str],
    top_modules: Optional[Sequence[str]],
) -> Optional[List[str]]:
    if top_modules:
        return [t.strip() for t in top_modules if t and str(t).strip()]
    if top_module:
        return [top_module]
    return None


def build_index_from_filelist(
    filelist_path: str,
    db_path: str,
    top_module: Optional[str] = None,
    *,
    top_modules: Optional[Sequence[str]] = None,
    elaborate: bool = False,
    batch_size: int = 0,
    resume: bool = True,
    force: bool = False,
    path_hierarchy_mode: str = "auto",
    elab_instance_cap: int = 50_000,
    elab_fast: bool = True,
    elab_deep: str = "auto",
    ifdef_compare: bool = False,
    ifdef_alt: Optional[str] = None,
    filelist_diff: Optional[str] = None,
    variants: Optional[Sequence[Tuple[str, Dict[str, str]]]] = None,
    variant_compare: Optional[Tuple[str, str]] = None,
    variant_dir: Optional[str] = None,
    on_progress: Optional[Callable[[int, int, str], None]] = None,
    on_phase: Optional[Callable[[str], None]] = None,
    index_cwd: Optional[str] = None,
    jobs: int = 0,
    blackbox_paths: Optional[Sequence[str]] = None,
    max_depth: Optional[int] = None,
    depth_anchor_patterns: Optional[Sequence[str]] = None,
    depth_anchor_inst_patterns: Optional[Sequence[str]] = None,
    depth_anchor_module_patterns: Optional[Sequence[str]] = None,
    depth_shallow: int = 2,
    depth_anchor_extra: Optional[int] = None,
    skim_parse: bool = True,
) -> HierarchyStore:
    def _phase(msg: str) -> None:
        if on_phase:
            on_phase(msg)

    from hch.ingest.kit_blackbox import resolve_blackbox_path_patterns

    bb_patterns = resolve_blackbox_path_patterns(blackbox_paths or ())

    cwd = resolve_index_cwd(filelist_path, index_cwd, os.environ)
    _phase(f"Expanding filelist: {filelist_path}")
    fl_early = parse_filelist_cached(filelist_path, index_cwd=str(cwd))
    _phase(
        f"Filelist ready: {len(fl_early.source_files)} sources, "
        f"{len(fl_early.incdirs)} incdirs, tier={'E' if elaborate else 'P'}"
    )
    slang_cache_path = Path(db_path)
    user_tops = _resolve_tops(top_module, top_modules)
    if not user_tops and fl_early.top_modules:
        user_tops = list(fl_early.top_modules)
    tops = user_tops
    primary_top = tops[0] if tops else top_module

    split_paths: Dict[str, str] = {}
    if variant_dir and variants and not elaborate:
        from hch.index.variant_split import build_variant_split_databases

        split_paths = build_variant_split_databases(
            filelist_path,
            variant_dir,
            variants,
            top_module=primary_top,
            top_modules=tops,
            path_hierarchy_mode=path_hierarchy_mode,
            index_cwd=str(cwd),
        )

    if variants and not elaborate:
        from hch.index.variant_index import build_index_variants, compare_variant_paths

        _phase(f"Indexing {len(variants)} ifdef variant(s)…")
        fl = fl_early
        meta = {
            "filelist": str(Path(filelist_path).resolve()),
            "filelist_index_cwd": str(cwd),
            "defines_json": json.dumps(fl.defines),
            "source_count": str(len(fl.source_files)),
            "tier": "P",
            "path_hierarchy_mode": path_hierarchy_mode,
        }
        store = build_index_variants(
            filelist_path,
            db_path,
            primary_top,
            variants,
            top_modules=tops,
            path_hierarchy_mode=path_hierarchy_mode,
            meta_extra=meta,
            index_cwd=str(cwd),
        )
        if split_paths:
            store.set_meta("variant_db_manifest_json", json.dumps(split_paths))
            store.set_meta("variant_split_dir", str(Path(variant_dir).resolve()))
        if variant_compare:
            diff = compare_variant_paths(store, variant_compare[0], variant_compare[1])
            store.set_meta("variant_diff_json", json.dumps(diff))
        return store

    from hch.index.parallel_parse import resolve_index_jobs

    worker_count = resolve_index_jobs(jobs) if not elaborate else 1
    effective_batch = batch_size
    if effective_batch <= 0 and not elaborate:
        n_src = len(fl_early.source_files)
        if n_src >= AUTO_BATCH_MIN_SOURCES:
            from hch.apps.index_progress import choose_auto_batch_size

            effective_batch = choose_auto_batch_size(n_src, jobs=worker_count)
            est_batches = (n_src + effective_batch - 1) // effective_batch
            jobs_note = f", {worker_count} workers" if worker_count > 1 else ""
            _phase(
                f"Auto batch mode: {n_src} sources → batch_size={effective_batch} "
                f"(~{est_batches} updates{jobs_note})"
            )

    from hch.ingest.parse_depth import ConditionalDepthPolicy

    depth_legacy = [p.strip() for p in (depth_anchor_patterns or []) if p and str(p).strip()]
    depth_inst = [
        p.strip() for p in (depth_anchor_inst_patterns or []) if p and str(p).strip()
    ]
    depth_module = [
        p.strip() for p in (depth_anchor_module_patterns or []) if p and str(p).strip()
    ]
    has_depth_anchors = bool(depth_legacy or depth_inst or depth_module)
    depth_policy: Optional[ConditionalDepthPolicy] = None
    if has_depth_anchors and primary_top:
        depth_policy = ConditionalDepthPolicy.from_sequences(
            depth_legacy,
            anchor_inst_patterns=depth_inst,
            anchor_module_patterns=depth_module,
            shallow_depth=depth_shallow,
            global_max_depth=max_depth,
            anchor_extra_depth=depth_anchor_extra,
        )
    if (max_depth is not None or has_depth_anchors) and not primary_top:
        _phase("WARNING: depth limits ignored without --top (cannot trim parse scope)")

    if effective_batch > 0 and not elaborate:
        _phase("Parsing sources (batched)…")
        return build_index_batched(
            filelist_path,
            db_path,
            top_module=primary_top,
            top_modules=tops,
            batch_size=effective_batch,
            resume=resume,
            force=force,
            path_hierarchy_mode=path_hierarchy_mode,
            on_progress=on_progress,
            on_phase=on_phase,
            on_heartbeat=on_phase,
            index_cwd=str(cwd),
            slang_cache_path=slang_cache_path,
            jobs=jobs,
            blackbox_path_patterns=bb_patterns,
            max_depth=max_depth,
            depth_policy=depth_policy,
            skim_parse=skim_parse,
        )

    fl = fl_early
    sources = [str(p) for p in fl.source_files]

    meta = {
        "filelist": str(Path(filelist_path).resolve()),
        "filelist_index_cwd": str(cwd),
        "defines_json": json.dumps(fl.defines),
        "source_count": str(len(fl.source_files)),
        "filelist_errors": json.dumps(fl.errors[:50]),
        "tier": "E" if elaborate else "P",
        "indexing_complete": "1",
        "path_hierarchy_mode": path_hierarchy_mode,
        "elab_instance_cap": str(elab_instance_cap),
        "elab_fast": "1" if elab_fast else "0",
        "elab_deep_mode": elab_deep,
    }
    if elab_deep == "closure":
        meta["elab_deep_closure_warning"] = (
            "closure mode may fail on duplicate module names; prefer hybrid or shallow"
        )

    if fl.top_modules:
        meta["filelist_top_modules_json"] = json.dumps(fl.top_modules)
    if fl.work_library:
        meta["work_library"] = fl.work_library

    if ifdef_compare and primary_top and ifdef_alt:
        from hch.ingest.ifdef_batch import compare_ifdef_for_index, diff_to_json

        diff = compare_ifdef_for_index(filelist_path, primary_top, ifdef_alt)
        meta["ifdef_variant_diff_json"] = diff_to_json(diff)

    if filelist_diff:
        from hch.ingest.filelist_diff import diff_filelists

        meta["filelist_diff_json"] = json.dumps(
            diff_filelists(filelist_path, filelist_diff)
        )

    apply_tier_contract_meta(meta)

    if elaborate:
        from hch.engine.elab_source_prune import build_module_path_index
        from hch.ingest.elab_fast_ingest import _compute_pruned_sources, tier_e_index_build
        from hch.index.hierarchy_mode import choose_hierarchy_mode
        from hch.index.path_elab_hybrid import (
            build_path_elab_hybrid_index,
            should_use_path_elab_hybrid_from_pruned,
        )

        top_list = tops or ([primary_top] if primary_top else [])
        pruned_bundle = _compute_pruned_sources(fl, top_list, max_pruned=256, max_ratio=0.08)
        pruned, _, _ = pruned_bundle
        mod_index = build_module_path_index([str(p) for p in fl.source_files])
        hybrid_heuristic = bool(
            primary_top
            and should_use_path_elab_hybrid_from_pruned(
                fl, primary_top, pruned or [], mod_index
            )
        )
        decision = choose_hierarchy_mode(
            elab_deep=elab_deep,
            primary_top=primary_top,
            pruned=pruned,
            mod_index=mod_index,
            fl=fl,
            use_hybrid_heuristic=hybrid_heuristic,
        )
        apply_tier_contract_meta(meta, decision=decision)
        if decision.use_path_elab_hybrid:
            _phase(f"Tier E hybrid index ({decision.mode})…")
            store = build_path_elab_hybrid_index(
                filelist_path,
                db_path,
                primary_top,
                fl,
                meta_extra=meta,
                elab_instance_cap=elab_instance_cap,
                elab_fast=elab_fast,
                slang_cache_path=str(slang_cache_path),
                index_cwd=str(cwd),
                on_phase=on_phase,
            )
            return store

        _phase(f"Tier E elaboration ({decision.mode})…")
        with _maybe_heartbeat(on_phase, f"Tier E elaboration ({decision.mode})"):
            modules, elab_result, ingest_meta = tier_e_index_build(
                fl,
                top_list,
                elab_fast=elab_fast,
                instance_cap=elab_instance_cap,
                pruned_bundle=pruned_bundle,
                slang_cache_path=str(slang_cache_path),
                index_cwd=str(cwd),
            )
        meta.update(ingest_meta)
        slang_fl = get_last_slang_filelist_path()
        if slang_fl:
            meta["slang_filelist_preprocessed"] = slang_fl
        return _build_elab_index(
            filelist_path,
            db_path,
            modules,
            fl=fl,
            top_modules=tops,
            top_module=primary_top,
            meta_extra=meta,
            elab_result=elab_result,
        )

    parse_sources = [str(p) for p in fl.source_files]
    if depth_policy is not None:
        from hch.ingest.parse_depth import select_parse_sources_conditional

        allowed = select_parse_sources_conditional(
            primary_top, parse_sources, depth_policy, fl.defines
        )
        skipped = len(parse_sources) - len(allowed)
        parse_sources = [s for s in parse_sources if s in allowed]
        _phase(
            f"Conditional depth (shallow={depth_shallow}): {len(parse_sources)} sources "
            f"(skipping {skipped})…"
        )
    elif max_depth is not None and primary_top:
        from hch.ingest.parse_depth import select_parse_sources_by_depth

        allowed = select_parse_sources_by_depth(
            primary_top, parse_sources, max_depth, fl.defines
        )
        skipped = len(parse_sources) - len(allowed)
        parse_sources = [s for s in parse_sources if s in allowed]
        _phase(
            f"Parse depth {max_depth}: {len(parse_sources)} sources "
            f"(skipping {skipped} below depth limit)…"
        )
    else:
        _phase(f"Parsing {len(fl.source_files)} sources (pyslang)…")
    with _maybe_heartbeat(on_phase, f"Parsing {len(parse_sources)} sources"):
        modules = ingest_filelist_result(
            fl,
            slang_cache_path=slang_cache_path,
            index_cwd=str(cwd),
            blackbox_path_patterns=bb_patterns,
            parse_source_paths=parse_sources if max_depth is not None else None,
        )
    _phase(f"Parsed {len(modules)} modules")
    meta.update(get_last_parse_meta())
    slang_fl = get_last_slang_filelist_path()
    if slang_fl:
        meta["slang_filelist_preprocessed"] = slang_fl

    flatten_tops: Optional[List[str]] = list(tops) if tops else None
    if user_tops:
        meta["top_modules_json"] = json.dumps(user_tops)
        meta["top_inference"] = "cli"
        flatten_primary = user_tops[0]
    else:
        from hch.ingest.top_infer import resolve_index_tops

        inferred = resolve_index_tops(modules, fl, filelist_path)
        meta["top_modules_json"] = json.dumps([inferred.primary])
        meta["top_modules_all_json"] = json.dumps(inferred.all_tops)
        meta["top_inference"] = inferred.method
        flatten_primary = inferred.primary
        flatten_tops = None

    from hch.ingest.kit_blackbox import flatten_roots_with_blackbox

    base_tops = flatten_tops if flatten_tops else (
        [flatten_primary] if flatten_primary else None
    )
    bb_flatten_tops, bb_boundary = flatten_roots_with_blackbox(
        modules,
        flatten_primary,
        base_tops,
        bb_patterns,
    )
    if bb_flatten_tops and len(bb_flatten_tops) > 1:
        meta["top_modules_json"] = json.dumps(bb_flatten_tops)
        meta["blackbox_orphan_roots_json"] = json.dumps(bb_flatten_tops[1:])
    use_single_top = len(bb_flatten_tops) == 1

    _phase("Flattening hierarchy and writing SQLite…")
    return build_index_from_modules(
        modules,
        db_path,
        top_module=bb_flatten_tops[0] if use_single_top else None,
        top_modules=None if use_single_top else bb_flatten_tops,
        meta_extra=meta,
        sources=sources,
        path_hierarchy_mode=path_hierarchy_mode,
        max_depth=max_depth,
        conditional_depth=depth_policy,
        blackbox_boundary_roots=bb_boundary,
    )


def _apply_flatten_meta(store: HierarchyStore) -> None:
    from hch.ingest.hierarchy_build import flatten_cycle_detected, get_flatten_warnings

    warns = get_flatten_warnings()
    if warns:
        store.set_meta("flatten_warnings_json", json.dumps(warns[:100]))
    if flatten_cycle_detected():
        store.set_meta("flatten_cycle_warning", "1")


def _multi_def_paths_from_modules(
    modules: Dict[str, ModuleRecord],
) -> Dict[str, List[str]]:
    from hch.ingest.multi_def import definition_paths_for_record

    out: Dict[str, List[str]] = {}
    for name, rec in modules.items():
        paths = definition_paths_for_record(rec)
        if len(paths) > 1:
            out[name] = paths
    return out


def _apply_parse_meta(store: HierarchyStore, modules: Dict[str, ModuleRecord]) -> None:
    gen_n = sum(1 for r in modules.values() for e in r.instances if e.in_generate)
    bind_n = sum(len(r.binds) for r in modules.values())
    bb_n = sum(1 for r in modules.values() if r.is_blackbox)
    multi_def_paths: Dict[str, List[str]] = {}
    for r in modules.values():
        raw = r.parameters.get("_definition_paths")
        if raw:
            try:
                paths = json.loads(raw)
                if isinstance(paths, list) and len(paths) > 1:
                    multi_def_paths[r.module_name] = paths
            except json.JSONDecodeError:
                pass
        attr = getattr(r, "_definition_paths", None)
        if attr and len(attr) > 1:
            multi_def_paths[r.module_name] = list(attr)
    multi_def = len(multi_def_paths)
    loop_unroll = int(get_last_parse_meta().get("generate_loop_unroll_count", "0") or 0)
    store.set_meta("tier_p_generate_unrolled", "1" if loop_unroll else "0")
    store.set_meta("generate_loop_unroll_count", str(loop_unroll))
    store.set_meta("generate_instance_count", str(gen_n))
    store.set_meta("bind_directive_count", str(bind_n))
    store.set_meta("library_blackbox_count", str(bb_n))
    store.set_meta("multi_def_module_count", str(multi_def))
    if multi_def_paths:
        store.set_meta("multi_def_modules_json", json.dumps(multi_def_paths))
    pkg_n = sum(1 for r in modules.values() if r.module_kind == "package")
    store.set_meta("package_module_count", str(pkg_n))
    macro_n = sum(1 for r in modules.values() for e in r.instances if e.from_macro)
    store.set_meta("macro_instance_count", str(macro_n))
    stats = get_last_parse_meta()
    for key in (
        "defparam_count",
        "primitive_count",
        "unsupported_filelist_opts_json",
        "generate_param_bound_unresolved_count",
        "case_generate_arm_count",
        "generate_branch_ambiguous_count",
        "modport_instance_count",
        "generate_loop_unroll_count",
        "macro_definition_count",
        "while_generate_placeholder_count",
        "while_generate_unroll_count",
        "parametric_array_expand_count",
        "generate_unreachable_edge_count",
        "generate_ambiguous_instance_count",
        "package_symbol_count",
        "package_module_count",
        "library_cell_map_json",
        "work_library",
        "filelist_top_modules_json",
        "parse_errors_json",
    ):
        if key in stats:
            store.set_meta(key, stats[key])
    pc = sum(
        1
        for r in modules.values()
        for e in r.instances
        if e.port_connections
    )
    store.set_meta("port_connection_edge_count", str(pc))


def _apply_index_warnings(
    store: HierarchyStore,
    modules: Dict[str, ModuleRecord],
    *,
    elab_errors: Optional[List[str]] = None,
    elab_warnings: Optional[List[str]] = None,
) -> None:
    from hch.ingest.unresolved import collect_unresolved_modules

    unresolved = collect_unresolved_modules(modules)
    warnings: List[str] = list(elab_warnings or [])
    if elab_errors:
        warnings.extend(elab_errors[:50])
    if unresolved:
        warnings.append(f"unresolved_modules: {', '.join(unresolved[:30])}")
    store.set_meta("unresolved_modules_json", json.dumps(unresolved))
    store.set_meta("warnings_json", json.dumps(warnings))


def _build_elab_index(
    filelist_path: str,
    db_path: str,
    modules: Dict[str, ModuleRecord],
    top_module: Optional[str] = None,
    top_modules: Optional[Sequence[str]] = None,
    meta_extra: Optional[dict] = None,
    elab_instance_cap: int = 50_000,
    fl: Optional[FilelistResult] = None,
    elab_result: Optional["ElaborationResult"] = None,
) -> HierarchyStore:
    from hch.engine.elab_result import ElaborationResult
    from hch.engine.pyslang_elab import elaborate_filelist

    mod_map = modules if isinstance(modules, dict) else {m.module_name: m for m in modules}
    store = HierarchyStore(db_path)
    store.load_modules(
        mod_map.values(),
        multi_def_paths_by_name=_multi_def_paths_from_modules(mod_map),
    )
    tops = _resolve_tops(top_module, top_modules)
    if elab_result is not None:
        result = elab_result
    else:
        result = elaborate_filelist(
            filelist_path,
            top_modules=tops,
            fl=fl,
            modules=mod_map,
            instance_cap=elab_instance_cap,
        )
    from hch.index.elab_param_merge import flat_instances_from_elab

    primary = tops[0] if tops else top_module
    flat = flat_instances_from_elab(
        result.instances, mod_map, top_module=primary
    )
    from hch.index.elab_bind_merge import merge_tier_p_bind_instances

    flat, bind_merge_added = merge_tier_p_bind_instances(
        flat, mod_map, top_module=primary or ""
    )
    elab_param_rows = sum(1 for row in flat if row.param_overrides)
    hierarchy_source = "elab"
    if result.partial:
        hierarchy_source = "elab_partial"
    has_elab_errors = bool(result.errors)
    if not flat and primary and primary in mod_map and not (
        result.partial and has_elab_errors
    ):
        flat = elaborate_flat(mod_map, top_module=primary, top_modules=tops)
        store.set_meta("elab_fallback", "tier_p")
        hierarchy_source = "tier_p_fallback"
    store.clear_instances()
    store.load_instances(flat)
    store.set_meta("engine", "pyslang")
    store.set_meta("tier", "E" if result.succeeded and flat else "P")
    store.set_meta("elab_succeeded", "1" if result.succeeded else "0")
    store.set_meta("elab_partial", "1" if result.partial else "0")
    store.set_meta("elab_errors_present", "1" if has_elab_errors else "0")
    store.set_meta(
        "elab_instance_cap_hit", "1" if result.instance_cap_hit else "0"
    )
    store.set_meta("hierarchy_source", hierarchy_source)
    store.set_meta("path_hierarchy_used", "0")
    store.set_meta("elab_param_instance_count", str(elab_param_rows))
    store.set_meta("tier_e_param_merge", "1")
    store.set_meta("tier_e_bind_merge", "1")
    store.set_meta("tier_e_bind_merge_added", str(bind_merge_added))
    _apply_index_warnings(
        store, mod_map, elab_errors=result.errors, elab_warnings=result.warnings
    )
    apply_tier_contract_meta(meta_extra or {})
    if meta_extra:
        for k, v in meta_extra.items():
            store.set_meta(k, v)
    store.set_meta("instance_count", str(store.count_instances()))
    return store


def build_index_from_modules(
    modules: Dict[str, ModuleRecord],
    db_path: str,
    top_module: Optional[str] = None,
    top_modules: Optional[Sequence[str]] = None,
    meta_extra: Optional[dict] = None,
    sources: Optional[List[str]] = None,
    path_hierarchy_mode: str = "auto",
    max_depth: Optional[int] = None,
    conditional_depth: Optional["ConditionalDepthPolicy"] = None,
    blackbox_boundary_roots: Optional[Set[str]] = None,
) -> HierarchyStore:
    from hch.ingest.unresolved import ensure_unresolved_module_stubs

    ensure_unresolved_module_stubs(modules)
    store = HierarchyStore(db_path)
    multi_paths = _multi_def_paths_from_modules(modules)
    store.load_modules(modules.values(), multi_def_paths_by_name=multi_paths)
    tops = _resolve_tops(top_module, top_modules)
    hierarchy_source = "ast"
    path_augmented = "0"
    single_top = tops and len(tops) == 1
    if sources and single_top:
        flat, hierarchy_source, path_augmented = elaborate_flat_with_sources(
            modules,
            sources=sources,
            top_module=tops[0],
            path_hierarchy_mode=path_hierarchy_mode,
            max_depth=max_depth,
            conditional_depth=conditional_depth,
            blackbox_boundary_roots=blackbox_boundary_roots,
        )
    else:
        flat = elaborate_flat(
            modules,
            top_module=top_module,
            top_modules=tops,
            max_depth=max_depth,
            conditional_depth=conditional_depth,
            blackbox_boundary_roots=blackbox_boundary_roots,
        )
    _apply_flatten_meta(store)
    store.clear_instances()
    store.load_instances(flat)
    store.set_meta("engine", "pyslang")
    store.set_meta("tier", "P")
    store.set_meta("hierarchy_source", hierarchy_source)
    store.set_meta(
        "path_hierarchy_used", "1" if hierarchy_source == "path" else "0"
    )
    store.set_meta("path_augmented", path_augmented)
    if max_depth is not None:
        store.set_meta("index_max_depth", str(max_depth))
    if conditional_depth is not None:
        store.set_meta(
            "depth_anchor_patterns_json",
            json.dumps(list(conditional_depth.anchor_legacy_patterns)),
        )
        store.set_meta(
            "depth_anchor_inst_json",
            json.dumps(list(conditional_depth.anchor_inst_patterns)),
        )
        store.set_meta(
            "depth_anchor_module_json",
            json.dumps(list(conditional_depth.anchor_module_patterns)),
        )
        store.set_meta("depth_shallow_limit", str(conditional_depth.shallow_depth))
        if conditional_depth.anchor_extra_depth is not None:
            store.set_meta(
                "depth_anchor_extra",
                str(conditional_depth.anchor_extra_depth),
            )
    _apply_parse_meta(store, modules)
    param_rows = sum(
        1
        for row in (
            store.conn.execute(
                "SELECT param_json FROM instances WHERE param_json IS NOT NULL AND param_json != '{}'"
            ).fetchall()
        )
    )
    store.set_meta("flat_param_instance_count", str(param_rows))
    mod_map = modules if isinstance(modules, dict) else {m.module_name: m for m in modules}
    _apply_index_warnings(store, mod_map)
    apply_tier_contract_meta(meta_extra or {})
    if meta_extra:
        for k, v in meta_extra.items():
            store.set_meta(k, v)
    store.set_meta("tier_contract_version", "1")
    store.set_meta("instance_count", str(store.count_instances()))
    return store