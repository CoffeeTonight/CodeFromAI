"""Build SQLite index from ingested modules."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from hch.ingest.filelist import FilelistResult, resolve_index_cwd
from hch.ingest.filelist_cache import parse_filelist_cached
from hch.ingest.filelist_config import get_last_slang_filelist_path
from hch.ingest.hierarchy_build import elaborate_flat, elaborate_flat_with_sources
from hch.ingest.ingest import get_last_parse_meta, ingest_filelist_result
from hch.index.batched_loader import build_index_batched
from hch.index.meta_contract import apply_tier_contract_meta
from hch.index.store import HierarchyStore
from hch.schema import FlatInstance, ModuleRecord


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
    index_cwd: Optional[str] = None,
) -> HierarchyStore:
    cwd = resolve_index_cwd(filelist_path, index_cwd, os.environ)
    fl_early = parse_filelist_cached(filelist_path, index_cwd=str(cwd))
    slang_cache_path = Path(db_path)
    tops = _resolve_tops(top_module, top_modules)
    if not tops and fl_early.top_modules:
        tops = list(fl_early.top_modules)
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

    if batch_size > 0 and not elaborate:
        return build_index_batched(
            filelist_path,
            db_path,
            top_module=primary_top,
            top_modules=tops,
            batch_size=batch_size,
            resume=resume,
            force=force,
            path_hierarchy_mode=path_hierarchy_mode,
            on_progress=on_progress,
            index_cwd=str(cwd),
            slang_cache_path=slang_cache_path,
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

    if tops:
        meta["top_modules_json"] = json.dumps(tops)
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
            )
            return store

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

    modules = ingest_filelist_result(
        fl, slang_cache_path=slang_cache_path, index_cwd=str(cwd)
    )
    meta.update(get_last_parse_meta())
    slang_fl = get_last_slang_filelist_path()
    if slang_fl:
        meta["slang_filelist_preprocessed"] = slang_fl
    return build_index_from_modules(
        modules,
        db_path,
        top_module=primary_top,
        top_modules=tops,
        meta_extra=meta,
        sources=sources,
        path_hierarchy_mode=path_hierarchy_mode,
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
) -> HierarchyStore:
    from hch.ingest.unresolved import ensure_unresolved_module_stubs

    ensure_unresolved_module_stubs(modules)
    store = HierarchyStore(db_path)
    multi_paths = _multi_def_paths_from_modules(modules)
    store.load_modules(modules.values(), multi_def_paths_by_name=multi_paths)
    tops = _resolve_tops(top_module, top_modules)
    primary = tops[0] if tops else top_module
    hierarchy_source = "ast"
    path_augmented = "0"
    multi_top = tops and len(tops) > 1
    if sources and primary and not multi_top:
        flat, hierarchy_source, path_augmented = elaborate_flat_with_sources(
            modules,
            sources=sources,
            top_module=primary,
            path_hierarchy_mode=path_hierarchy_mode,
        )
    else:
        flat = elaborate_flat(modules, top_module=primary, top_modules=tops)
    _apply_flatten_meta(store)
    store.load_instances(flat)
    store.set_meta("engine", "pyslang")
    store.set_meta("tier", "P")
    store.set_meta("hierarchy_source", hierarchy_source)
    store.set_meta(
        "path_hierarchy_used", "1" if hierarchy_source == "path" else "0"
    )
    store.set_meta("path_augmented", path_augmented)
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