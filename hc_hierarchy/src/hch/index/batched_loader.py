"""Batched filelist indexing with checkpoint / resume (Phase 7)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

from hch.apps.index_progress import ProgressHeartbeat
from hch.index.parallel_parse import (
    _CHECKPOINT_COMMIT_EVERY,
    resolve_index_jobs,
    run_parallel_batches,
    run_skim_batches,
)
from hch.ingest.filelist import FilelistResult, parse_filelist_simple
from hch.ingest.kit_blackbox import (
    kit_blackbox_meta,
    partition_sources,
    reapply_kit_blackbox_overlay,
    scan_kit_blackbox_modules,
)
from hch.ingest.parse_depth import ConditionalDepthPolicy
from hch.ingest.hierarchy_build import elaborate_flat_with_sources
from hch.ingest.merge import merge_module_records
from hch.index.store import HierarchyStore
from hch.schema import ModuleRecord


def _checkpoint_done(store: HierarchyStore) -> Set[str]:
    raw = store.get_meta("checkpoint_files", "[]")
    try:
        return set(json.loads(raw))
    except json.JSONDecodeError:
        return set()


def _save_checkpoint(
    store: HierarchyStore,
    done: Set[str],
    *,
    commit: bool = True,
) -> None:
    store.set_meta("checkpoint_files", json.dumps(sorted(done)), commit=commit)


def build_index_batched(
    filelist_path: str,
    db_path: str,
    top_module: Optional[str] = None,
    *,
    top_modules: Optional[List[str]] = None,
    batch_size: int = 64,
    resume: bool = True,
    force: bool = False,
    path_hierarchy_mode: str = "auto",
    on_progress: Optional[Callable[[int, int, str], None]] = None,
    on_phase: Optional[Callable[[str], None]] = None,
    on_heartbeat: Optional[Callable[[str], None]] = None,
    index_cwd: Optional[str] = None,
    slang_cache_path: Optional[str] = None,
    jobs: int = 1,
    blackbox_path_patterns: Optional[List[str]] = None,
    max_depth: Optional[int] = None,
    depth_policy: Optional["ConditionalDepthPolicy"] = None,
    skim_parse: bool = True,
) -> HierarchyStore:
    """
    Ingest sources in batches; persist modules after each batch for resume.
    """
    fl = parse_filelist_simple(filelist_path, index_cwd=index_cwd)
    if not fl.source_files:
        raise ValueError(f"No sources in filelist: {fl.errors}")

    store = HierarchyStore(db_path)
    fl_key = str(Path(filelist_path).resolve())

    if force:
        store.conn.execute("DELETE FROM instance_ports")
        store.conn.execute("DELETE FROM modules")
        store.conn.execute("DELETE FROM instances")
        store.conn.execute("DELETE FROM files WHERE filepath != ''")
        store.set_meta("checkpoint_files", "[]")
        store.set_meta("indexing_complete", "0")
        store.conn.commit()
        done: Set[str] = set()
    else:
        done = _checkpoint_done(store) if resume else set()
        prev_fl = store.get_meta("filelist")
        if resume and prev_fl and prev_fl != fl_key:
            raise ValueError(
                f"DB built from different filelist ({prev_fl}); use --force to rebuild"
            )

    patterns = list(blackbox_path_patterns or [])
    defines = dict(fl.defines)
    all_sources = [str(p.resolve()) for p in fl.source_files]
    parse_sources, kit_sources = partition_sources(all_sources, patterns)
    sources = parse_sources
    full_sources: Optional[Set[str]] = None
    skim_sources: Optional[Set[str]] = None
    if depth_policy is not None and top_module:
        from hch.ingest.parse_depth import (
            classify_parse_sources_conditional,
            select_parse_sources_conditional,
        )

        if skim_parse:
            full_set, skim_set = classify_parse_sources_conditional(
                top_module, sources, depth_policy, defines
            )
            allowed = full_set | skim_set
            full_sources = full_set
            skim_sources = skim_set
        else:
            allowed = select_parse_sources_conditional(
                top_module, sources, depth_policy, defines
            )
        skipped_depth = len(sources) - len(allowed)
        sources = [s for s in sources if s in allowed]
        if on_phase:
            if skim_parse and skim_sources is not None and full_sources is not None:
                on_phase(
                    f"Conditional depth (shallow={depth_policy.shallow_depth}): "
                    f"{len(sources)} sources "
                    f"({len(full_sources)} pyslang, {len(skim_sources)} text-skim, "
                    f"skipping {skipped_depth})…"
                )
            else:
                on_phase(
                    f"Conditional depth (shallow={depth_policy.shallow_depth}): "
                    f"{len(sources)} sources (skipping {skipped_depth})…"
                )
    elif max_depth is not None and top_module:
        from hch.ingest.parse_depth import select_parse_sources_by_depth

        allowed = select_parse_sources_by_depth(
            top_module, sources, max_depth, defines
        )
        skipped_depth = len(sources) - len(allowed)
        sources = [s for s in sources if s in allowed]
        if on_phase:
            on_phase(
                f"Parse depth {max_depth}: {len(sources)} sources "
                f"(skipping {skipped_depth} below depth limit)…"
            )
    total = len(all_sources)
    pending_all = [s for s in sources if s not in done]
    pending_skim: List[str] = []
    pending_full: List[str] = []
    if (
        skim_parse
        and skim_sources is not None
        and full_sources is not None
        and depth_policy is not None
    ):
        pending_skim = [s for s in pending_all if s in skim_sources]
        pending_full = [s for s in pending_all if s in full_sources]
    else:
        pending_full = list(pending_all)
    inc = [str(p) for p in fl.incdirs]

    store.set_meta("filelist", fl_key, commit=False)
    store.set_meta("defines_json", json.dumps(defines), commit=False)
    store.set_meta("source_count", str(total), commit=False)
    worker_count = resolve_index_jobs(jobs)
    store.set_meta("tier", "P", commit=False)
    store.set_meta("engine", "pyslang", commit=False)
    store.set_meta("index_jobs", str(worker_count), commit=False)
    if max_depth is not None:
        store.set_meta("index_max_depth", str(max_depth), commit=False)
    if depth_policy is not None:
        import json as _json

        store.set_meta(
            "depth_anchor_patterns_json",
            _json.dumps(list(depth_policy.anchor_legacy_patterns)),
            commit=False,
        )
        store.set_meta(
            "depth_anchor_inst_json",
            _json.dumps(list(depth_policy.anchor_inst_patterns)),
            commit=False,
        )
        store.set_meta(
            "depth_anchor_module_json",
            _json.dumps(list(depth_policy.anchor_module_patterns)),
            commit=False,
        )
        store.set_meta(
            "depth_shallow_limit",
            str(depth_policy.shallow_depth),
            commit=False,
        )
        if depth_policy.anchor_extra_depth is not None:
            store.set_meta(
                "depth_anchor_extra",
                str(depth_policy.anchor_extra_depth),
                commit=False,
            )
        store.set_meta(
            "index_skim_parse",
            "1" if skim_parse else "0",
            commit=False,
        )
    store.conn.commit()

    modules_acc: Dict[str, ModuleRecord] = store.load_all_modules() if resume else {}
    kit_mods: Dict[str, ModuleRecord] = {}
    if kit_sources and on_phase:
        on_phase(
            f"Kit blackbox: {len(kit_sources)} sources (header scan only, no parse)…"
        )
    if kit_sources:
        kit_mods = scan_kit_blackbox_modules(kit_sources, defines=defines)
        merge_module_records(modules_acc, kit_mods)
        if kit_mods:
            store.load_modules(kit_mods.values(), commit=True)
        done.update(kit_sources)
        _save_checkpoint(store, done)
        if on_progress:
            on_progress(len(done), total, kit_sources[-1])
    for key, val in kit_blackbox_meta(patterns, kit_sources, kit_mods).items():
        store.set_meta(key, val, commit=False)
    if kit_mods:
        store.conn.commit()
    hb = on_heartbeat or on_phase
    if done and on_phase:
        on_phase(f"Resuming checkpoint: {len(done)}/{total} sources already parsed")
    lib_files = [str(p) for p in fl.library_files]
    lib_dirs = [str(p) for p in fl.library_dirs]

    def _make_batches(paths: List[str]) -> List[Tuple[int, List[str]]]:
        if not paths:
            return []
        return [
            (batch_idx, paths[i : i + batch_size])
            for batch_idx, i in enumerate(range(0, len(paths), batch_size), start=1)
        ]

    skim_batches = _make_batches(pending_skim)
    full_batches = _make_batches(pending_full)
    total_parse_batches = len(skim_batches) + len(full_batches)
    completed_batches = 0
    milestone = max(1, total_parse_batches // 20) if total_parse_batches >= 20 else 0

    def _on_batch_done(
        batch_idx: int,
        chunk: List[str],
        batch_mods: Dict[str, ModuleRecord],
        *,
        label: str,
        batch_total: int,
    ) -> None:
        nonlocal completed_batches
        merge_module_records(modules_acc, batch_mods)
        store.load_modules(batch_mods.values(), commit=False)
        done.update(chunk)
        completed_batches += 1
        should_commit = (
            completed_batches % _CHECKPOINT_COMMIT_EVERY == 0
            or completed_batches == total_parse_batches
        )
        if should_commit:
            _save_checkpoint(store, done, commit=False)
            store.conn.commit()
        if on_phase and milestone and completed_batches % milestone == 0:
            on_phase(f"{label} batch {completed_batches}/{batch_total}…")
        processed = len(done)
        if on_progress:
            on_progress(processed, total, chunk[-1] if chunk else "")
        elif label == "Parse":
            print(
                f"[hch-index] {processed}/{total} sources "
                f"(+{len(chunk)} batch, {len(modules_acc)} modules)",
                file=sys.stderr,
            )

    if pending_skim and on_phase:
        skim_bs = len(skim_batches)
        if worker_count > 1:
            on_phase(
                f"Text-skim {len(pending_skim)} shallow sources "
                f"({skim_bs} batches, {worker_count} workers)…"
            )
        else:
            on_phase(f"Text-skim {len(pending_skim)} shallow sources ({skim_bs} batches)…")

    if pending_skim:
        with ProgressHeartbeat(hb, f"Text-skim {len(skim_batches)} batches"):
            run_skim_batches(
                skim_batches,
                defines=defines,
                jobs=worker_count,
                on_batch_done=lambda idx, chunk, mods: _on_batch_done(
                    idx,
                    chunk,
                    mods,
                    label="Text-skim",
                    batch_total=total_parse_batches,
                ),
            )
        store.set_meta("parse_skim_count", str(len(pending_skim)), commit=False)

    if pending_full and on_phase:
        full_bs = len(full_batches)
        if worker_count > 1:
            on_phase(
                f"Parsing {len(pending_full)} anchor sources in {full_bs} batches "
                f"({worker_count} workers)…"
            )
        else:
            on_phase(f"Parsing {len(pending_full)} anchor sources in {full_bs} batches…")

    if pending_full:
        hb_label = (
            f"Parsing {len(full_batches)} batches ({worker_count} workers)"
            if worker_count > 1
            else f"Parsing {len(full_batches)} batches"
        )
        with ProgressHeartbeat(hb, hb_label):
            run_parallel_batches(
                full_batches,
                include_dirs=inc,
                defines=defines,
                library_files=lib_files,
                library_dirs=lib_dirs,
                jobs=worker_count,
                on_batch_done=lambda idx, chunk, mods: _on_batch_done(
                    idx,
                    chunk,
                    mods,
                    label="Parse",
                    batch_total=total_parse_batches,
                ),
            )
        store.set_meta("parse_full_count", str(len(pending_full)), commit=False)
        store.conn.commit()

    if kit_sources and patterns:
        reapply_kit_blackbox_overlay(modules_acc, kit_mods, kit_sources, patterns)

    if on_phase:
        on_phase(
            f"Flattening hierarchy ({len(modules_acc)} modules, {total} sources)…"
        )
    store.clear_instances()
    flatten_tops = list(top_modules) if top_modules else None
    if top_module or top_modules:
        primary = (top_modules[0] if top_modules else top_module) or top_module
        store.set_meta("top_modules_json", json.dumps(top_modules or [top_module]))
        store.set_meta("top_inference", "cli", commit=False)
    else:
        from hch.ingest.top_infer import resolve_index_tops

        inferred = resolve_index_tops(modules_acc, fl, filelist_path)
        primary = inferred.primary
        flatten_tops = None
        store.set_meta("top_modules_json", json.dumps([primary]), commit=False)
        store.set_meta("top_modules_all_json", json.dumps(inferred.all_tops), commit=False)
        store.set_meta("top_inference", inferred.method, commit=False)
    from hch.ingest.kit_blackbox import flatten_roots_with_blackbox

    bb_flatten_tops, bb_boundary = flatten_roots_with_blackbox(
        modules_acc,
        primary,
        flatten_tops if flatten_tops else ([primary] if primary else None),
        patterns,
    )
    if bb_flatten_tops and bb_flatten_tops != (flatten_tops or []):
        flatten_tops = bb_flatten_tops
        store.set_meta("top_modules_json", json.dumps(bb_flatten_tops), commit=False)
        store.set_meta("blackbox_orphan_roots_json", json.dumps(bb_flatten_tops[1:]), commit=False)
    with ProgressHeartbeat(hb, "Flattening hierarchy"):
        from hch.ingest.parse_depth import load_deepened_prefixes

        deepened = load_deepened_prefixes(
            {r[0]: r[1] for r in store.conn.execute("SELECT key, value FROM meta")}
        )
        flat, hierarchy_source, path_augmented = elaborate_flat_with_sources(
            modules_acc,
            sources=all_sources,
            top_module=primary if len(bb_flatten_tops) == 1 else None,
            top_modules=bb_flatten_tops if len(bb_flatten_tops) != 1 else None,
            path_hierarchy_mode=path_hierarchy_mode,
            max_depth=max_depth,
            conditional_depth=depth_policy,
            deepened_prefixes=deepened,
            blackbox_boundary_roots=bb_boundary,
        )
    store.load_instances(flat)
    store.set_meta("hierarchy_source", hierarchy_source)
    store.set_meta(
        "path_hierarchy_used", "1" if hierarchy_source == "path" else "0"
    )
    store.set_meta("path_augmented", path_augmented)
    store.set_meta("indexing_complete", "1")
    store.set_meta("instance_count", str(store.count_instances()))
    store.set_meta("module_count", str(store.count_modules()))
    return store