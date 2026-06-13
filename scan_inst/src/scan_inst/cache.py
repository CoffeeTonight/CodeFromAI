"""Disk cache for DesignIndex and per-top elaboration results."""

from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from scan_inst.filelist import FilelistResult, filelist_provenance_maps
from scan_inst.index import DesignIndex
from scan_inst.manifest import (
    SourceManifest,
    build_source_manifest,
    config_cache_key,
    manifest_diff,
    manifest_is_current,
)
from scan_inst.models import ElabNode, FlatRow
from scan_inst.preprocess import preprocess_sources

CACHE_VERSION = 2


@dataclass
class ScanInstCacheBundle:
    version: int
    config_key: str
    source_manifest: SourceManifest
    index: DesignIndex
    elab: Dict[str, Tuple[ElabNode, List[FlatRow]]] = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        return self.config_key


def default_cache_dir() -> Path:
    import os

    env = os.environ.get("SCAN_INST_CACHE_DIR")
    if env:
        return Path(env)
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        return Path(xdg) / "scan-inst"
    return Path.home() / ".cache" / "scan-inst"


def cache_path_for(cache_dir: Path, config_key: str) -> Path:
    return cache_dir / f"{config_key}.scan-inst.pkl"


def elab_cache_key(top: str, max_depth: Optional[int]) -> str:
    depth = -1 if max_depth is None else max_depth
    return f"{top}\x00{depth}"


def load_cache(path: Path) -> Optional[ScanInstCacheBundle]:
    if not path.is_file():
        return None
    try:
        with path.open("rb") as fh:
            obj = pickle.load(fh)
    except (OSError, pickle.PickleError, EOFError, ValueError):
        return None
    if isinstance(obj, ScanInstCacheBundle):
        if obj.version != CACHE_VERSION:
            return None
        return obj
    return None


def save_cache(path: Path, bundle: ScanInstCacheBundle) -> None:
    bundle.index.strip_bodies_for_cache()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("wb") as fh:
        pickle.dump(bundle, fh, protocol=pickle.HIGHEST_PROTOCOL)
    tmp.replace(path)


def build_design_index(
    fl: FilelistResult,
    *,
    ignore_paths: Sequence[str],
    ignore_path_files: Sequence[str],
    ignore_modules: Sequence[str],
    jobs: int,
    on_progress: Optional[Callable[[str], None]] = None,
    source_subset: Optional[Sequence[str]] = None,
) -> DesignIndex:
    sources = (
        [str(p) for p in fl.source_files]
        if source_subset is None
        else list(source_subset)
    )
    if on_progress:
        on_progress(
            f"index: building from {len(sources)} sources "
            f"({len(fl.filelist_info)} filelists)"
        )
    pre = preprocess_sources(
        sources,
        [str(p) for p in fl.include_dirs],
        fl.defines,
        jobs=jobs,
        on_progress=on_progress,
    )
    via_map, chain_map = filelist_provenance_maps(fl)
    return DesignIndex.build(
        pre,
        library_files=[str(p) for p in fl.library_files],
        library_dirs=[str(p) for p in fl.library_dirs],
        libexts=list(fl.libexts),
        ignore_paths=list(ignore_paths),
        ignore_path_files=list(ignore_path_files),
        ignore_modules=list(ignore_modules),
        jobs=jobs,
        on_progress=on_progress,
        file_via_filelist=via_map,
        file_filelist_chain=chain_map,
        filelist_info=fl.filelist_info,
        filelist_children=fl.filelist_children,
        filelist_edges=fl.filelist_edges,
    )


def _incremental_update(
    bundle: ScanInstCacheBundle,
    fl: FilelistResult,
    manifest: SourceManifest,
    *,
    changed: set[str],
    removed: set[str],
    added: set[str],
    ignore_paths: Sequence[str],
    ignore_path_files: Sequence[str],
    ignore_modules: Sequence[str],
    jobs: int,
    on_progress: Optional[Callable[[str], None]] = None,
) -> DesignIndex:
    touch = sorted(changed | added)
    if on_progress:
        on_progress(
            f"cache: incremental update ({len(touch)} changed/new, "
            f"{len(removed)} removed)"
        )
    pre = preprocess_sources(
        touch,
        [str(p) for p in fl.include_dirs],
        fl.defines,
        jobs=jobs,
        on_progress=on_progress,
    )
    bundle.index.patch_files(
        pre,
        touch,
        sorted(removed),
        jobs=jobs,
        on_progress=on_progress,
    )
    bundle.source_manifest = dict(manifest)
    return bundle.index


def load_or_build_index(
    filelist_path: str | Path,
    fl: FilelistResult,
    *,
    cache_dir: Path,
    extra_defines: Mapping[str, str],
    ignore_paths: Sequence[str],
    ignore_path_files: Sequence[str],
    ignore_modules: Sequence[str],
    jobs: int,
    use_cache: bool,
    refresh_cache: bool,
    on_progress: Optional[Callable[[str], None]] = None,
) -> tuple[DesignIndex, ScanInstCacheBundle, bool, bool, bool, Path]:
    """
    Return (index, bundle, index_cache_hit, rebuilt_index, incremental, cache_path).

    ``index_cache_hit`` is True on a full manifest match (no RTL rescan).
    ``incremental`` is True when only changed sources were rescanned.
    """
    config_key = config_cache_key(
        filelist_path,
        fl,
        cache_version=CACHE_VERSION,
        extra_defines=extra_defines,
        ignore_paths=ignore_paths,
        ignore_path_files=ignore_path_files,
        ignore_modules=ignore_modules,
    )
    path = cache_path_for(cache_dir, config_key)
    manifest = build_source_manifest(fl, ignore_path_files=ignore_path_files)
    bundle: Optional[ScanInstCacheBundle] = None
    index_cache_hit = False
    rebuilt_index = True
    incremental = False

    if use_cache and not refresh_cache:
        if on_progress:
            on_progress("cache: checking index cache")
        bundle = load_cache(path)
        if bundle is not None and bundle.config_key == config_key:
            if manifest_is_current(bundle.source_manifest, manifest):
                index_cache_hit = True
                rebuilt_index = False
                if on_progress:
                    on_progress(
                        f"cache: loaded index ({len(bundle.index.modules)} modules)"
                    )
                return bundle.index, bundle, True, False, False, path
            changed, removed, added = manifest_diff(bundle.source_manifest, manifest)
            if changed or removed or added:
                index = _incremental_update(
                    bundle,
                    fl,
                    manifest,
                    changed=changed,
                    removed=removed,
                    added=added,
                    ignore_paths=ignore_paths,
                    ignore_path_files=ignore_path_files,
                    ignore_modules=ignore_modules,
                    jobs=jobs,
                    on_progress=on_progress,
                )
                save_cache(path, bundle)
                if on_progress:
                    on_progress(
                        f"cache: incremental save ({len(index.modules)} modules)"
                    )
                incremental = True
                rebuilt_index = True
                return index, bundle, False, rebuilt_index, incremental, path
        if on_progress and path.is_file():
            on_progress("cache: stale or unreadable, rebuilding index")

    if on_progress:
        on_progress("index: building (no cache hit)")
    index = build_design_index(
        fl,
        ignore_paths=ignore_paths,
        ignore_path_files=ignore_path_files,
        ignore_modules=ignore_modules,
        jobs=jobs,
        on_progress=on_progress,
    )
    bundle = ScanInstCacheBundle(
        version=CACHE_VERSION,
        config_key=config_key,
        source_manifest=dict(manifest),
        index=index,
        elab=bundle.elab if bundle is not None else {},
    )
    if use_cache:
        if on_progress:
            on_progress(f"cache: saving index ({len(index.modules)} modules)")
        save_cache(path, bundle)
    elif on_progress:
        on_progress(f"index: done ({len(index.modules)} modules)")
    return index, bundle, index_cache_hit, rebuilt_index, incremental, path


def get_cached_elab(
    bundle: ScanInstCacheBundle,
    top: str,
    max_depth: Optional[int],
) -> Optional[Tuple[ElabNode, List[FlatRow]]]:
    return bundle.elab.get(elab_cache_key(top, max_depth))


def store_cached_elab(
    bundle: ScanInstCacheBundle,
    top: str,
    max_depth: Optional[int],
    root: ElabNode,
    rows: List[FlatRow],
    *,
    cache_dir: Path,
    use_cache: bool,
) -> bool:
    key = elab_cache_key(top, max_depth)
    bundle.elab[key] = (root, rows)
    if not use_cache:
        return False
    path = cache_path_for(cache_dir, bundle.config_key)
    save_cache(path, bundle)
    return True