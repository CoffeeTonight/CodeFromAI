"""Ninja-style parallel batch parsing for Tier P indexing."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from hch.schema import ModuleRecord

_CHECKPOINT_COMMIT_EVERY = 4


def resolve_index_jobs(jobs: int) -> int:
    """Map CLI --jobs to worker count (0 = auto, capped at 32)."""
    if jobs < 0:
        raise ValueError("--jobs must be >= 0")
    if jobs == 0:
        return min(os.cpu_count() or 1, 32)
    return jobs


def _parse_source_batch(
    chunk: Sequence[str],
    include_dirs: Sequence[str],
    defines: Dict[str, str],
    library_files: Sequence[str],
    library_dirs: Sequence[str],
) -> Dict[str, ModuleRecord]:
    from hch.ingest.ingest import ingest_source_files

    return ingest_source_files(
        list(chunk),
        include_dirs=list(include_dirs),
        defines=dict(defines),
        library_files=list(library_files),
        library_dirs=list(library_dirs),
    )


def run_parallel_batches(
    batches: List[Tuple[int, List[str]]],
    *,
    include_dirs: List[str],
    defines: Dict[str, str],
    library_files: List[str],
    library_dirs: List[str],
    jobs: int,
    on_batch_done: Callable[[int, List[str], Dict[str, ModuleRecord]], None],
) -> None:
    """Parse batches with a fixed worker pool; persist results on the main thread."""
    if jobs <= 1 or len(batches) <= 1:
        for batch_idx, chunk in batches:
            mods = _parse_source_batch(
                chunk, include_dirs, defines, library_files, library_dirs
            )
            on_batch_done(batch_idx, chunk, mods)
        return

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        future_map = {
            pool.submit(
                _parse_source_batch,
                chunk,
                include_dirs,
                defines,
                library_files,
                library_dirs,
            ): (batch_idx, chunk)
            for batch_idx, chunk in batches
        }
        for future in as_completed(future_map):
            batch_idx, chunk = future_map[future]
            on_batch_done(batch_idx, chunk, future.result())


def _skim_source_batch(
    chunk: Sequence[str],
    defines: Optional[Mapping[str, str]],
) -> Dict[str, ModuleRecord]:
    from hch.ingest.text_skim import ingest_sources_text_skim

    return ingest_sources_text_skim(list(chunk), defines=defines)


def run_skim_batches(
    batches: List[Tuple[int, List[str]]],
    *,
    defines: Optional[Mapping[str, str]] = None,
    jobs: int,
    on_batch_done: Callable[[int, List[str], Dict[str, ModuleRecord]], None],
) -> None:
    """Text-only skim ingest in parallel batches (no pyslang)."""
    if jobs <= 1 or len(batches) <= 1:
        for batch_idx, chunk in batches:
            mods = _skim_source_batch(chunk, defines)
            on_batch_done(batch_idx, chunk, mods)
        return

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        future_map = {
            pool.submit(_skim_source_batch, chunk, defines): (batch_idx, chunk)
            for batch_idx, chunk in batches
        }
        for future in as_completed(future_map):
            batch_idx, chunk = future_map[future]
            on_batch_done(batch_idx, chunk, future.result())