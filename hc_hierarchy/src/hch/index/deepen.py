"""On-demand pyslang deepen for shallow / depth-capped branches."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from hch.index.parallel_parse import resolve_index_jobs, run_parallel_batches
from hch.index.store import HierarchyStore
from hch.ingest.filelist import parse_filelist_simple
from hch.ingest.hierarchy_build import elaborate_flat_with_sources
from hch.ingest.merge import merge_module_records
from hch.ingest.parse_depth import (
    ConditionalDepthPolicy,
    _UNLIMITED,
    collect_deepen_sources,
    load_deepened_prefixes,
    save_deepened_prefixes,
)
from hch.schema import ModuleRecord


@dataclass(frozen=True)
class DeepenResult:
    under_path: str
    files_parsed: int
    modules_upgraded: int
    instances_before: int
    instances_after: int
    deepened_paths: Tuple[str, ...]


def _module_name_at_path(store: HierarchyStore, full_path: str) -> Optional[str]:
    row = store.conn.execute(
        """
        SELECT m.module_name
        FROM instances i
        JOIN modules m ON m.id = i.module_id
        WHERE i.full_path = ?
        LIMIT 1
        """,
        (full_path,),
    ).fetchone()
    return row[0] if row else None


def _load_anchor_list(meta: Mapping[str, str], key: str) -> List[str]:
    raw = meta.get(key, "").strip()
    if not raw:
        return []
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(loaded, list):
        return [str(p).strip() for p in loaded if str(p).strip()]
    return []


def _depth_policy_from_meta(meta: Mapping[str, str]) -> Optional[ConditionalDepthPolicy]:
    legacy = _load_anchor_list(meta, "depth_anchor_patterns_json")
    inst = _load_anchor_list(meta, "depth_anchor_inst_json")
    module = _load_anchor_list(meta, "depth_anchor_module_json")
    if not (legacy or inst or module):
        return None
    shallow = int(meta.get("depth_shallow_limit") or "2")
    max_raw = meta.get("index_max_depth")
    global_max = int(max_raw) if max_raw not in (None, "") else None
    extra_raw = meta.get("depth_anchor_extra")
    anchor_extra = int(extra_raw) if extra_raw not in (None, "") else None
    return ConditionalDepthPolicy.from_sequences(
        legacy,
        anchor_inst_patterns=inst,
        anchor_module_patterns=module,
        shallow_depth=shallow,
        global_max_depth=global_max,
        anchor_extra_depth=anchor_extra,
    )


def _top_modules_from_meta(meta: Mapping[str, str]) -> List[str]:
    raw = meta.get("top_modules_json", "").strip()
    if not raw:
        return []
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(loaded, list):
        return [str(t).strip() for t in loaded if str(t).strip()]
    return []


def deepen_branch(
    db_path: str,
    under_path: str,
    *,
    extra_depth: Optional[int] = None,
    full_subtree: bool = False,
    jobs: int = 0,
    on_phase: Optional[Callable[[str], None]] = None,
) -> DeepenResult:
    """
    Re-parse and expand hierarchy below *under_path* with pyslang.

    *full_subtree* (default when *extra_depth* is None): unlimited depth below path.
    *extra_depth*: parse only N additional instance levels below *under_path*.
    """
    under_path = under_path.strip()
    if not under_path:
        raise ValueError("under_path is required")

    store = HierarchyStore(db_path)
    try:
        if store.get_meta("indexing_complete", "0") != "1":
            raise ValueError("Index incomplete; run hch-index first")

        mod_name = _module_name_at_path(store, under_path)
        if not mod_name:
            raise ValueError(f"Instance path not found in index: {under_path}")

        meta_rows = {
            r[0]: r[1]
            for r in store.conn.execute("SELECT key, value FROM meta").fetchall()
        }
        filelist = meta_rows.get("filelist", "").strip()
        if not filelist or not Path(filelist).exists():
            raise ValueError(f"filelist missing or not found in DB meta: {filelist!r}")

        index_cwd = meta_rows.get("filelist_index_cwd") or None
        defines = json.loads(meta_rows.get("defines_json") or "{}")
        fl = parse_filelist_simple(filelist, index_cwd=index_cwd)
        all_sources = [str(p.resolve()) for p in fl.source_files]

        depth_policy = _depth_policy_from_meta(meta_rows)
        deepened = list(load_deepened_prefixes(meta_rows))
        if under_path not in deepened:
            deepened.append(under_path)
        save_deepened_prefixes(store, deepened, commit=False)

        hops = _UNLIMITED if full_subtree or extra_depth is None else extra_depth
        modules_acc = store.load_all_modules()
        parse_files = collect_deepen_sources(
            under_path,
            mod_name,
            all_sources,
            modules_acc,
            defines,
            extra_hops=hops,
        )
        if not parse_files:
            raise ValueError(f"No RTL sources to deepen under {under_path}")

        if on_phase:
            mode = "full subtree" if hops == _UNLIMITED else f"+{hops} levels"
            on_phase(
                f"Deepen {under_path} ({mode}): pyslang {len(parse_files)} sources…"
            )

        inc = [str(p) for p in fl.incdirs]
        lib_files = [str(p) for p in fl.library_files]
        lib_dirs = [str(p) for p in fl.library_dirs]
        worker_count = resolve_index_jobs(jobs)
        batches = [(1, sorted(parse_files))]

        upgraded = 0

        def _on_batch(_idx: int, chunk: List[str], batch_mods: Dict[str, ModuleRecord]) -> None:
            nonlocal upgraded
            for rec in batch_mods.values():
                rec.parse_tier = "full"
            upgraded += len(batch_mods)
            merge_module_records(modules_acc, batch_mods)
            store.load_modules(batch_mods.values(), commit=False)

        run_parallel_batches(
            batches,
            include_dirs=inc,
            defines=defines,
            library_files=lib_files,
            library_dirs=lib_dirs,
            jobs=worker_count,
            on_batch_done=_on_batch,
        )
        store.conn.commit()

        inst_before = store.count_instances()
        tops = _top_modules_from_meta(meta_rows)
        primary = tops[0] if tops else None
        path_mode = meta_rows.get("path_hierarchy_mode", "auto")
        max_depth = None
        if meta_rows.get("index_max_depth"):
            max_depth = int(meta_rows["index_max_depth"])

        if on_phase:
            on_phase(f"Re-flattening after deepen ({len(modules_acc)} modules)…")

        store.clear_instances()
        flat, hierarchy_source, path_augmented = elaborate_flat_with_sources(
            modules_acc,
            sources=all_sources,
            top_module=primary,
            top_modules=tops if tops else None,
            path_hierarchy_mode=path_mode,
            max_depth=max_depth,
            conditional_depth=depth_policy,
            deepened_prefixes=tuple(deepened),
        )
        store.load_instances(flat)
        store.set_meta("hierarchy_source", hierarchy_source)
        store.set_meta("path_hierarchy_used", "1" if hierarchy_source == "path" else "0")
        store.set_meta("path_augmented", path_augmented)
        store.set_meta("instance_count", str(store.count_instances()))
        store.set_meta("module_count", str(store.count_modules()))
        store.set_meta("deepen_count", str(int(meta_rows.get("deepen_count") or "0") + 1))
        store.conn.commit()

        inst_after = store.count_instances()
        return DeepenResult(
            under_path=under_path,
            files_parsed=len(parse_files),
            modules_upgraded=upgraded,
            instances_before=inst_before,
            instances_after=inst_after,
            deepened_paths=tuple(deepened),
        )
    finally:
        store.close()