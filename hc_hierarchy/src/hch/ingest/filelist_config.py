"""Map FilelistResult → pyslang driver / preprocessing config."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Sequence, Union

from hch.engine.pyslang_parse import PyslangParseConfig
from hch.ingest.compile_context import PyslangCompileContext
from hch.ingest.filelist import FilelistResult

_last_slang_filelist_path: Optional[str] = None


def get_last_slang_filelist_path() -> Optional[str]:
    return _last_slang_filelist_path


def _remember_ctx(ctx: PyslangCompileContext) -> PyslangParseConfig:
    global _last_slang_filelist_path
    if ctx.slang_filelist_preprocessed:
        _last_slang_filelist_path = ctx.slang_filelist_preprocessed
    elif ctx.filelist_path:
        _last_slang_filelist_path = ctx.filelist_path
    return ctx.to_parse_config()


def config_for_pruned_elab(
    fl: FilelistResult,
    pruned_sources: Sequence[str],
    *,
    index_cwd: Optional[Union[str, Path]] = None,
    slang_cache_path: Optional[Union[str, Path]] = None,
) -> PyslangParseConfig:
    """pyslang config for closure compile only (no full preprocessed .f reload)."""
    ctx = PyslangCompileContext.for_pruned_closure(
        fl,
        pruned_sources,
        index_cwd=index_cwd,
        slang_cache_path=slang_cache_path,
    )
    return _remember_ctx(ctx)


def supplemental_library_sources(
    library_files: Sequence[Union[str, Path]],
    library_dirs: Sequence[Union[str, Path]],
    *,
    libexts: Sequence[str],
) -> List[str]:
    from hch.ingest.compile_context import supplemental_library_sources as _sup

    return _sup(library_files, library_dirs, libexts=libexts)


def config_from_filelist(
    fl: FilelistResult,
    *,
    include_lib_sources: bool = True,
    index_cwd: Optional[Union[str, Path]] = None,
    slang_cache_path: Optional[Union[str, Path]] = None,
) -> PyslangParseConfig:
    ctx = PyslangCompileContext.from_filelist(
        fl,
        include_lib_sources=include_lib_sources,
        index_cwd=index_cwd,
        slang_cache_path=slang_cache_path,
    )
    return _remember_ctx(ctx)