"""
Minimal .f filelist reader for hc_hierarchy (self-contained).

Expansion (-f / -F) lives in :mod:`filelist_preprocess`; this module keeps the
public API and :class:`FilelistResult` type stable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Union

from hch.ingest.filelist_cwd import resolve_index_cwd
from hch.ingest.filelist_preprocess import (
    FilelistResult,
    build_slang_filelist_lines,
    expand_filelist,
    preprocess_filelist_for_slang,
    slang_filelist_cache_path,
    write_slang_filelist,
    write_slang_filelist_cached,
)

__all__ = [
    "FilelistResult",
    "parse_filelist_simple",
    "preprocess_filelist_for_slang",
    "build_slang_filelist_lines",
    "write_slang_filelist",
    "write_slang_filelist_cached",
    "slang_filelist_cache_path",
    "expand_filelist",
    "resolve_index_cwd",
]


def parse_filelist_simple(
    top_filelist: str,
    env: Optional[Dict[str, str]] = None,
    *,
    index_cwd: Optional[Union[str, Path]] = None,
) -> FilelistResult:
    """
    Parse and expand a top filelist.

    ``index_cwd`` sets the run directory for ``-F`` (default: directory of the top .f).
    """
    return expand_filelist(top_filelist, env, index_cwd=index_cwd)