"""Tier E for synthetic deep RTL: path hierarchy + shallow slang closure."""

from __future__ import annotations

import json
from typing import Dict, List, Optional, Sequence, Tuple

from hch.ingest.filelist import FilelistResult
from hch.ingest.hierarchy_build import _path_hierarchy_depth_count
from hch.index.store import HierarchyStore
from hch.schema import FlatInstance, ModuleRecord

__all__ = [
    "should_use_path_elab_hybrid",
    "build_path_elab_hybrid_index",
    "closure_duplicate_stats",
]


def closure_duplicate_stats(
    paths: Sequence[str],
    module_index: Dict[str, List[str]],
) -> Dict[str, int]:
    """Count modules with multiple RTL files among ``paths``."""
    from pathlib import Path

    from hch.ingest.path_hierarchy import module_name_from_file

    path_to_mod: Dict[str, str] = {}
    for mod, hits in module_index.items():
        for raw in hits:
            path_to_mod[str(Path(raw).resolve())] = mod

    per_mod: Dict[str, int] = {}
    for raw in paths:
        key = str(Path(raw).resolve())
        mod = path_to_mod.get(key) or module_name_from_file(key)
        if mod:
            per_mod[mod] = per_mod.get(mod, 0) + 1
    multi = sum(1 for c in per_mod.values() if c > 1)
    return {
        "pruned_files": len(paths),
        "modules_touched": len(per_mod),
        "multi_def_in_closure": multi,
    }


def should_use_path_elab_hybrid(
    fl: FilelistResult,
    top_module: Optional[str],
    *,
    pruned_count: int = 0,
    max_pruned: int = 256,
    path_depth_threshold: int = 10,
    module_index: Optional[Dict[str, List[str]]] = None,
) -> bool:
    """Heuristic when only pruned_count is known (no file list)."""
    if not top_module:
        return False
    sources = [str(p.resolve()) for p in fl.source_files]
    if _path_hierarchy_depth_count(sources) < path_depth_threshold:
        return False
    return pruned_count > max_pruned


def should_use_path_elab_hybrid_from_pruned(
    fl: FilelistResult,
    top_module: Optional[str],
    pruned: Sequence[str],
    module_index: Dict[str, List[str]],
    *,
    max_pruned: int = 256,
    path_depth_threshold: int = 10,
) -> bool:
    sources = [str(p.resolve()) for p in fl.source_files]
    if not top_module or _path_hierarchy_depth_count(sources) < path_depth_threshold:
        return False
    if len(pruned) > max_pruned:
        return True
    full_stats = closure_duplicate_stats(sources, module_index)
    if len(sources) > 64 and full_stats["multi_def_in_closure"] >= 8:
        return True
    stats = closure_duplicate_stats(pruned, module_index)
    return stats["multi_def_in_closure"] > 0 and len(pruned) > 32


def build_path_elab_hybrid_index(
    filelist_path: str,
    db_path: str,
    top_module: str,
    fl: FilelistResult,
    *,
    meta_extra: Optional[dict] = None,
    elab_instance_cap: int = 50_000,
    elab_fast: bool = True,
    slang_cache_path: Optional[str] = None,
    index_cwd: Optional[str] = None,
) -> HierarchyStore:
    """
    Deep synthetic index: ~991 path instances + shallow Tier E slang (closure).

    ``elab_succeeded`` reflects shallow slang; hierarchy is path-complete.
    """
    from hch.engine.elab_source_prune import build_module_path_index
    from hch.index.elab_bind_merge import merge_tier_p_bind_instances
    from hch.index.elab_param_merge import flat_instances_from_elab
    from hch.index.loader import _apply_index_warnings, _resolve_tops
    from hch.ingest.elab_fast_ingest import _compute_pruned_sources, tier_e_index_build
    from hch.ingest.hierarchy_build import elaborate_flat_with_sources
    from hch.ingest.path_hierarchy import augment_instance_edges_from_paths

    tops = _resolve_tops(top_module, None) or [top_module]
    primary = tops[0]
    sources = [str(p.resolve()) for p in fl.source_files]
    mod_index = build_module_path_index(sources)

    pruned_bundle = _compute_pruned_sources(fl, tops, max_pruned=256, max_ratio=0.08)
    pruned, prune_meta, _ = pruned_bundle

    mods, elab_result, ingest_meta = tier_e_index_build(
        fl,
        tops,
        elab_fast=elab_fast,
        instance_cap=elab_instance_cap,
        pruned_bundle=pruned_bundle,
        slang_cache_path=slang_cache_path,
        index_cwd=index_cwd,
    )

    for name, paths in mod_index.items():
        if name not in mods:
            mods[name] = ModuleRecord(module_name=name, file_path=paths[0])
        elif not mods[name].file_path and paths:
            mods[name].file_path = paths[0]

    path_edges = augment_instance_edges_from_paths(
        mods, sources, top_module=primary
    )
    flat_path, hierarchy_source, path_augmented = elaborate_flat_with_sources(
        mods,
        sources=sources,
        top_module=primary,
        path_hierarchy_mode="on",
    )
    flat_elab = flat_instances_from_elab(
        elab_result.instances, mods, top_module=primary
    )
    elab_by_path = {row.full_path: row for row in flat_elab}

    merged: List[FlatInstance] = []
    shallow_overlay = 0
    for row in flat_path:
        hit = elab_by_path.get(row.full_path)
        if hit:
            shallow_overlay += 1
            if hit.param_overrides:
                row.param_overrides = {**row.param_overrides, **hit.param_overrides}
            if hit.file:
                row.file = hit.file
            if hit.ports:
                row.ports = hit.ports
        merged.append(row)

    flat, bind_added = merge_tier_p_bind_instances(merged, mods, top_module=primary)

    from hch.index.loader import _multi_def_paths_from_modules

    store = HierarchyStore(db_path)
    store.load_modules(
        mods.values(),
        multi_def_paths_by_name={**mod_index, **_multi_def_paths_from_modules(mods)},
    )
    store.load_instances(flat)

    dup_stats = closure_duplicate_stats(sources, mod_index)
    multi_def_paths = {
        name: paths for name, paths in mod_index.items() if len(paths) > 1
    }
    meta = {
        "tier": "E",
        "engine": "pyslang",
        "hierarchy_source": "path_elab_hybrid",
        "path_hierarchy_used": "1",
        "path_augmented": path_augmented,
        "path_edges_added": str(path_edges),
        "shallow_elab_instances": str(len(flat_elab)),
        "shallow_path_overlay_count": str(shallow_overlay),
        "path_instance_count": str(len(flat_path)),
        "elab_succeeded": "1" if elab_result.succeeded else "0",
        "shallow_elab_succeeded": "1" if elab_result.succeeded else "0",
        "elab_partial": "1" if elab_result.partial else "0",
        "elab_errors_present": "1" if elab_result.errors else "0",
        "elab_closure_hybrid": "1",
        "closure_multi_def_modules": str(dup_stats["multi_def_in_closure"]),
        "multi_def_module_count": str(len(multi_def_paths)),
        "multi_def_modules_json": (
            json.dumps(multi_def_paths) if multi_def_paths else ""
        ),
        "ingest_mode": ingest_meta.get("ingest_mode", "fast"),
        "ingest_source_count": ingest_meta.get("ingest_source_count", ""),
        "ingest_pruned_from": ingest_meta.get("ingest_pruned_from", ""),
        "elab_fast_ingest": ingest_meta.get("elab_fast_ingest", "0"),
        "tier_e_single_pass": ingest_meta.get("tier_e_single_pass", "0"),
        "tier_e_param_merge": "1",
        "tier_e_bind_merge": "1",
        "tier_e_bind_merge_added": str(bind_added),
        "instance_count": str(len(flat)),
    }
    if meta_extra:
        meta.update(meta_extra)
    from hch.ingest.filelist_config import get_last_slang_filelist_path

    slang_fl = get_last_slang_filelist_path()
    if slang_fl:
        meta["slang_filelist_preprocessed"] = slang_fl
    for k, v in meta.items():
        store.set_meta(k, v)
    prune_meta_keys = ("elab_closure_pruned", "elab_closure_ratio")
    for k in prune_meta_keys:
        if k in prune_meta:
            store.set_meta(k, prune_meta[k])

    _apply_index_warnings(
        store,
        mods,
        elab_errors=elab_result.errors,
        elab_warnings=elab_result.warnings,
    )
    return store