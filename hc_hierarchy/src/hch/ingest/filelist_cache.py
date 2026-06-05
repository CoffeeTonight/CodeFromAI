"""Cache parsed filelists by (path, index_cwd, mtime) to avoid repeated nested -f expansion."""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Set

from hch.ingest.filelist import FilelistResult, parse_filelist_simple
from hch.ingest.filelist_cwd import resolve_index_cwd


@dataclass
class _CacheEntry:
    result: FilelistResult
    filelist_mtimes: Dict[str, float]
    index_cwd: str


_cache: Dict[str, _CacheEntry] = {}


def clear_filelist_cache() -> None:
    _cache.clear()


def _cache_key(top: Path, index_cwd: Path) -> str:
    return f"{top}\0{index_cwd}"


def collect_filelist_mtimes(
    top: Path,
    *,
    index_cwd: Optional[Path] = None,
) -> Dict[str, float]:
    """Snapshot mtimes for top .f and nested -f/-F filelists (EDA path rules)."""
    top = top.resolve()
    cwd = index_cwd or resolve_index_cwd(top)
    out: Dict[str, float] = {}
    if not top.exists():
        return out
    seen: Set[Path] = set()
    queue: deque[Path] = deque([top])
    while queue:
        fl = queue.popleft()
        if fl in seen:
            continue
        seen.add(fl)
        if not fl.exists():
            continue
        key = str(fl)
        try:
            out[key] = fl.stat().st_mtime
        except OSError:
            continue
        try:
            text = fl.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        base = fl.parent
        for raw in text.splitlines():
            line = re.sub(r"//.*", "", raw).strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 1)
            if len(parts) < 2:
                continue
            flag, rest = parts[0], parts[1].strip().strip('"').strip("'")
            if flag not in ("-f", "-F"):
                continue
            nested = Path(rest)
            if not nested.is_absolute():
                nested = (base if flag == "-f" else cwd) / nested
            queue.append(nested.resolve())
    return out


def _entry_stale(entry: _CacheEntry) -> bool:
    for path, mt in entry.filelist_mtimes.items():
        p = Path(path)
        if not p.exists():
            return True
        try:
            if p.stat().st_mtime != mt:
                return True
        except OSError:
            return True
    return False


def parse_filelist_cached(
    top_filelist: str,
    env: Optional[Dict[str, str]] = None,
    *,
    index_cwd: Optional[str] = None,
    clear: bool = False,
) -> FilelistResult:
    if clear:
        _cache.clear()
    top = Path(top_filelist).resolve()
    cwd = resolve_index_cwd(top, index_cwd, env)
    key = _cache_key(top, cwd)
    entry = _cache.get(key)
    if entry is not None and not _entry_stale(entry):
        return entry.result
    fl = parse_filelist_simple(str(top), env=env, index_cwd=str(cwd))
    mtimes = collect_filelist_mtimes(top, index_cwd=cwd)
    _cache[key] = _CacheEntry(result=fl, filelist_mtimes=mtimes, index_cwd=str(cwd))
    return fl