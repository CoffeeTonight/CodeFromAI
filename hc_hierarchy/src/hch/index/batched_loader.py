"""Batched filelist indexing with checkpoint / resume (Phase 7)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set

from hch.apps.index_progress import ProgressHeartbeat
from hch.ingest.filelist import FilelistResult, parse_filelist_simple
from hch.ingest.hierarchy_build import elaborate_flat_with_sources
from hch.ingest.ingest import ingest_source_files
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

    sources = [str(p.resolve()) for p in fl.source_files]
    pending = [s for s in sources if s not in done]
    inc = [str(p) for p in fl.incdirs]
    defines = dict(fl.defines)

    store.set_meta("filelist", fl_key, commit=False)
    store.set_meta("defines_json", json.dumps(defines), commit=False)
    store.set_meta("source_count", str(len(sources)), commit=False)
    store.set_meta("tier", "P", commit=False)
    store.set_meta("engine", "pyslang", commit=False)
    store.conn.commit()

    total = len(sources)
    modules_acc: Dict[str, ModuleRecord] = store.load_all_modules() if resume else {}
    hb = on_heartbeat or on_phase
    if done and on_phase:
        on_phase(f"Resuming checkpoint: {len(done)}/{total} sources already parsed")
    num_batches = (len(pending) + batch_size - 1) // batch_size if pending else 0
    if on_phase and num_batches > 1:
        on_phase(f"Parsing {len(pending)} pending sources in {num_batches} batches…")

    for batch_idx, i in enumerate(range(0, len(pending), batch_size), start=1):
        chunk = pending[i : i + batch_size]
        if on_phase and num_batches >= 20 and batch_idx % max(1, num_batches // 20) == 0:
            on_phase(f"Parse batch {batch_idx}/{num_batches}…")
        with ProgressHeartbeat(hb, f"Parsing batch {batch_idx}/{num_batches}"):
            batch_mods = ingest_source_files(
                chunk,
                include_dirs=inc,
                defines=defines,
                library_files=[str(p) for p in fl.library_files],
                library_dirs=[str(p) for p in fl.library_dirs],
            )
        merge_module_records(modules_acc, batch_mods)
        store.load_modules(batch_mods.values(), commit=True)
        done.update(chunk)
        _save_checkpoint(store, done)
        processed = len(done)
        if on_progress:
            on_progress(processed, total, chunk[-1] if chunk else "")
        else:
            print(
                f"[hch-index] {processed}/{total} sources "
                f"(+{len(chunk)} batch, {len(modules_acc)} modules)",
                file=sys.stderr,
            )

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
    with ProgressHeartbeat(hb, "Flattening hierarchy"):
        flat, hierarchy_source, path_augmented = elaborate_flat_with_sources(
            modules_acc,
            sources=sources,
            top_module=primary if flatten_tops else None,
            top_modules=flatten_tops,
            path_hierarchy_mode=path_hierarchy_mode,
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