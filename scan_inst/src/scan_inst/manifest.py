"""Source manifest for fast cache validation and incremental index."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence, Tuple

from scan_inst.filelist import FilelistResult

SourceStat = Tuple[int, int]  # mtime_ns, size
SourceManifest = Dict[str, SourceStat]


def path_stat(path: Path) -> Optional[SourceStat]:
    try:
        st = path.stat()
        return st.st_mtime_ns, st.st_size
    except OSError:
        return None


def build_source_manifest(
    fl: FilelistResult,
    *,
    ignore_path_files: Sequence[str] = (),
) -> SourceManifest:
    manifest: SourceManifest = {}
    for src in fl.source_files:
        key = str(src.resolve())
        stat = path_stat(src)
        if stat is not None:
            manifest[key] = stat
    for lib in fl.library_files:
        key = str(lib.resolve())
        stat = path_stat(lib)
        if stat is not None:
            manifest[key] = stat
    for fl_path in fl.filelist_info:
        p = Path(fl_path)
        key = str(p.resolve())
        stat = path_stat(p)
        if stat is not None:
            manifest[key] = stat
    for raw in ignore_path_files:
        p = Path(raw)
        key = str(p.resolve())
        stat = path_stat(p)
        if stat is not None:
            manifest[key] = stat
    return manifest


def manifest_diff(
    old: Mapping[str, SourceStat],
    new: SourceManifest,
) -> tuple[set[str], set[str], set[str]]:
    old_keys = set(old)
    new_keys = set(new)
    added = new_keys - old_keys
    removed = old_keys - new_keys
    changed = {
        key
        for key in old_keys & new_keys
        if old[key] != new[key]
    }
    return changed, removed, added


def manifest_is_current(old: Mapping[str, SourceStat], new: SourceManifest) -> bool:
    if set(old) != set(new):
        return False
    return all(old[key] == new[key] for key in new)


def _feed(hasher: "hashlib._Hash", text: str) -> None:
    hasher.update(text.encode("utf-8"))
    hasher.update(b"\0")


def _feed_mapping(hasher: "hashlib._Hash", data: Mapping[str, str]) -> None:
    for key in sorted(data):
        _feed(hasher, key)
        _feed(hasher, str(data[key]))


def _feed_patterns(hasher: "hashlib._Hash", patterns: Sequence[str]) -> None:
    for pat in sorted(set(patterns)):
        _feed(hasher, pat)


def config_cache_key(
    filelist_path: str | Path,
    fl: FilelistResult,
    *,
    cache_version: int,
    extra_defines: Mapping[str, str],
    ignore_paths: Sequence[str],
    ignore_path_files: Sequence[str],
    ignore_modules: Sequence[str],
    ignore_filelists: Sequence[str],
) -> str:
    """Stable cache filename key (no per-source stats)."""
    hasher = hashlib.sha256()
    _feed(hasher, f"version={cache_version}")
    p = Path(filelist_path)
    _feed(hasher, str(p.resolve()))
    try:
        st = p.stat()
        hasher.update(str(st.st_mtime_ns).encode())
        hasher.update(str(st.st_size).encode())
    except OSError:
        _feed(hasher, "missing")
    if fl.index_cwd_used:
        _feed(hasher, f"index_cwd={fl.index_cwd_used.resolve()}")
    defines = dict(fl.defines)
    for key, val in extra_defines.items():
        defines[key] = val
    _feed_mapping(hasher, defines)
    _feed_patterns(hasher, ignore_paths)
    _feed_patterns(hasher, ignore_modules)
    _feed_patterns(hasher, ignore_filelists)
    for ignore_file in sorted(ignore_path_files):
        ip = Path(ignore_file)
        _feed(hasher, str(ip.resolve()))
        stat = path_stat(ip)
        if stat is not None:
            hasher.update(str(stat[0]).encode())
            hasher.update(str(stat[1]).encode())
    for inc in sorted(fl.include_dirs, key=lambda x: str(x)):
        _feed(hasher, str(inc.resolve()))
    for libdir in sorted(fl.library_dirs, key=lambda x: str(x)):
        _feed(hasher, str(libdir.resolve()))
    for ext in fl.libexts:
        _feed(hasher, ext)
    return hasher.hexdigest()


def scan_chunksize(num_tasks: int, workers: int) -> int:
    if num_tasks <= 64:
        return 1
    return max(1, min(64, num_tasks // max(workers * 4, 1)))