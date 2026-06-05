"""Compare two filelists for indexing meta (A5)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from hch.ingest.filelist import parse_filelist_simple


def diff_filelists(
    primary: str,
    other: str,
    *,
    env: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    a = parse_filelist_simple(primary, env=env)
    b = parse_filelist_simple(other, env=env)

    def _norm(paths):
        return sorted({str(Path(p).resolve()) for p in paths})

    src_a, src_b = _norm(a.source_files), _norm(b.source_files)
    y_a, y_b = _norm(a.library_dirs), _norm(b.library_dirs)
    v_a, v_b = _norm(a.library_files), _norm(b.library_files)

    return {
        "primary": str(Path(primary).resolve()),
        "other": str(Path(other).resolve()),
        "only_primary_sources": sorted(set(src_a) - set(src_b)),
        "only_other_sources": sorted(set(src_b) - set(src_a)),
        "only_primary_y": sorted(set(y_a) - set(y_b)),
        "only_other_y": sorted(set(y_b) - set(y_a)),
        "only_primary_v": sorted(set(v_a) - set(v_b)),
        "only_other_v": sorted(set(v_b) - set(v_a)),
        "define_diff": {
            k: {"primary": a.defines.get(k), "other": b.defines.get(k)}
            for k in sorted(set(a.defines) | set(b.defines))
            if a.defines.get(k) != b.defines.get(k)
        },
        "errors": {"primary": a.errors[:20], "other": b.errors[:20]},
    }