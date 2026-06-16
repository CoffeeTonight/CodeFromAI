"""
Path-walk module DB: Tier-0 regex decl index + Tier-1 validated instance scan.

Built incrementally during path-walk; disk cache per RTL file (regex + validated).
Does not participate in full DesignIndex build / load_or_build_index.
"""

from __future__ import annotations

import hashlib
import os
import pickle
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Set, Tuple

from scan_inst.ignore_path import source_path_matches
from scan_inst.index import DesignIndex, scan_preprocessed
from scan_inst.inst_scan import expand_inst_names
from scan_inst.manifest import path_stat
from scan_inst.models import InstanceEdge, ModuleRecord
from scan_inst.params import resolve_param_map

PATH_WALK_DB_VERSION = 1

_MODULE_DECL_RE = re.compile(
    r"^\s*(?:module|interface|program)\s+([A-Za-z_]\w*)\b",
    re.MULTILINE | re.IGNORECASE,
)


@dataclass(frozen=True)
class _FileRegexCacheEntry:
    mtime_ns: int
    size: int
    module_names: Tuple[str, ...]


@dataclass(frozen=True)
class _FileValidatedCacheEntry:
    mtime_ns: int
    size: int
    defines_digest: str
    modules: Tuple[Tuple[str, ModuleRecord], ...]


def _defines_digest(defines: Mapping[str, str]) -> str:
    hasher = hashlib.sha256()
    for key in sorted(defines):
        hasher.update(key.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(str(defines[key]).encode("utf-8"))
        hasher.update(b"\0")
    return hasher.hexdigest()[:16]


def _file_cache_token(path: str) -> str:
    return hashlib.sha256(str(Path(path).resolve()).encode("utf-8")).hexdigest()[:20]


def path_walk_db_cache_key(
    sources: Sequence[str | Path],
    *,
    defines: Mapping[str, str],
    include_dirs: Sequence[str | Path] = (),
    skip_path_patterns: Sequence[str] = (),
) -> str:
    """Stable namespace for path-walk DB sidecars (independent of full-index cache)."""
    hasher = hashlib.sha256()
    hasher.update(f"pw-db-v={PATH_WALK_DB_VERSION}".encode())
    for raw in sorted({str(Path(s).resolve()) for s in sources}):
        hasher.update(raw.encode())
        hasher.update(b"\0")
        stat = path_stat(Path(raw))
        if stat is not None:
            hasher.update(str(stat[0]).encode())
            hasher.update(str(stat[1]).encode())
    for raw in sorted({str(Path(p).resolve()) for p in include_dirs}):
        hasher.update(b"inc:")
        hasher.update(raw.encode())
        hasher.update(b"\0")
    for pat in sorted(set(skip_path_patterns)):
        hasher.update(b"skip:")
        hasher.update(pat.encode())
        hasher.update(b"\0")
    hasher.update(_defines_digest(defines).encode())
    return hasher.hexdigest()


def tier0_regex_module_names(text: str) -> List[str]:
    """Fast declaration harvest (no preprocess). May include ifdef-gated names."""
    names: List[str] = []
    seen: Set[str] = set()
    for m in _MODULE_DECL_RE.finditer(text):
        name = m.group(1)
        if name not in seen:
            seen.add(name)
            names.append(name)
    return names


def _record_lite(rec: ModuleRecord) -> ModuleRecord:
    return ModuleRecord(
        module_name=rec.module_name,
        file_path=rec.file_path,
        body="",
        raw_params=dict(rec.raw_params),
        instances=list(rec.instances),
        needs_generate_fold=rec.needs_generate_fold,
        is_blackbox=rec.is_blackbox,
        is_interface=rec.is_interface,
        stop_reason=rec.stop_reason,
    )


class PathWalkModuleDb:
    """
    Incremental module→files map (Tier 0) and per-file validated scan (Tier 1).

    Tier 1 uses light preprocess + instance scan; Tier 0 hits are always confirmed
    before use.
    """

    def __init__(
        self,
        sources: Sequence[str | Path],
        index: DesignIndex,
        *,
        include_dirs: Sequence[str | Path] = (),
        defines: Optional[Mapping[str, str]] = None,
        skip_path_patterns: Sequence[str] = (),
        cache_dir: Optional[Path] = None,
        cache_key: Optional[str] = None,
        no_cache: bool = False,
    ) -> None:
        self._sources = [str(Path(s).resolve()) for s in sources]
        self._index = index
        self._include_dirs = [Path(p) for p in include_dirs]
        self._defines = dict(defines or {})
        self._skip = tuple(skip_path_patterns)
        self._no_cache = no_cache
        self._defines_digest = _defines_digest(self._defines)

        base = cache_dir
        if base is None and not no_cache:
            from scan_inst.cache import default_cache_dir

            base = default_cache_dir()
        self._cache_root: Optional[Path] = None
        if base is not None and cache_key and not no_cache:
            self._cache_root = Path(base) / "path-walk-db" / cache_key

        self._module_to_files: Dict[str, List[str]] = {}
        self._file_to_modules: Dict[str, List[str]] = {}
        self._prefer_file: Dict[str, str] = {}
        self._regex_scanned: Set[str] = set()
        self._regex_queue: List[str] = []
        self._validated_memory: Dict[str, Dict[str, ModuleRecord]] = {}
        self.files_regex_scanned: int = 0
        self.files_validated: int = 0
        self.cache_regex_hits: int = 0
        self.cache_validated_hits: int = 0

    def remember_index_modules(self) -> None:
        for name, rec in self._index.modules.items():
            if rec.file_path:
                self._note_regex_modules(rec.file_path, [name])
                self._prefer_file.setdefault(name, str(Path(rec.file_path).resolve()))

    def _regex_sidecar(self, path: str) -> Optional[Path]:
        if self._cache_root is None:
            return None
        return self._cache_root / "regex" / f"{_file_cache_token(path)}.pkl"

    def _validated_sidecar(self, path: str) -> Optional[Path]:
        if self._cache_root is None:
            return None
        return (
            self._cache_root
            / "validated"
            / f"{_file_cache_token(path)}_{self._defines_digest}.pkl"
        )

    def _load_regex_sidecar(self, path: str) -> Optional[_FileRegexCacheEntry]:
        sidecar = self._regex_sidecar(path)
        if sidecar is None or not sidecar.is_file():
            return None
        try:
            with sidecar.open("rb") as fh:
                obj = pickle.load(fh)
        except (OSError, pickle.PickleError, EOFError, ValueError):
            return None
        if not isinstance(obj, _FileRegexCacheEntry):
            return None
        stat = path_stat(Path(path))
        if stat is None or stat != (obj.mtime_ns, obj.size):
            return None
        return obj

    def _save_regex_sidecar(self, path: str, names: Sequence[str]) -> None:
        sidecar = self._regex_sidecar(path)
        if sidecar is None:
            return
        stat = path_stat(Path(path))
        if stat is None:
            return
        entry = _FileRegexCacheEntry(stat[0], stat[1], tuple(names))
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        tmp = sidecar.with_suffix(sidecar.suffix + ".tmp")
        with tmp.open("wb") as fh:
            pickle.dump(entry, fh, protocol=pickle.HIGHEST_PROTOCOL)
        tmp.replace(sidecar)

    def _load_validated_sidecar(self, path: str) -> Optional[Dict[str, ModuleRecord]]:
        sidecar = self._validated_sidecar(path)
        if sidecar is None or not sidecar.is_file():
            return None
        try:
            with sidecar.open("rb") as fh:
                obj = pickle.load(fh)
        except (OSError, pickle.PickleError, EOFError, ValueError):
            return None
        if not isinstance(obj, _FileValidatedCacheEntry):
            return None
        stat = path_stat(Path(path))
        if stat is None or stat != (obj.mtime_ns, obj.size):
            return None
        if obj.defines_digest != self._defines_digest:
            return None
        return {name: _record_lite(rec) for name, rec in obj.modules}

    def _save_validated_sidecar(
        self,
        path: str,
        modules: Mapping[str, ModuleRecord],
    ) -> None:
        sidecar = self._validated_sidecar(path)
        if sidecar is None:
            return
        stat = path_stat(Path(path))
        if stat is None:
            return
        entry = _FileValidatedCacheEntry(
            stat[0],
            stat[1],
            self._defines_digest,
            tuple((n, _record_lite(r)) for n, r in sorted(modules.items())),
        )
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        tmp = sidecar.with_suffix(sidecar.suffix + ".tmp")
        with tmp.open("wb") as fh:
            pickle.dump(entry, fh, protocol=pickle.HIGHEST_PROTOCOL)
        tmp.replace(sidecar)

    def _note_regex_modules(self, path: str, names: Iterable[str]) -> None:
        key = str(Path(path).resolve())
        file_names = self._file_to_modules.setdefault(key, [])
        for name in names:
            if not name:
                continue
            if name not in file_names:
                file_names.append(name)
            files = self._module_to_files.setdefault(name, [])
            if key not in files:
                files.append(key)

    def _tier0_scan_file(self, path: str) -> List[str]:
        key = str(Path(path).resolve())
        if key in self._regex_scanned:
            return list(self._file_to_modules.get(key, []))
        self._regex_scanned.add(key)
        if self._skip and source_path_matches(key, self._skip):
            self.files_regex_scanned += 1
            return []

        hit = self._load_regex_sidecar(key)
        if hit is not None:
            self.cache_regex_hits += 1
            names = list(hit.module_names)
            self._note_regex_modules(key, names)
            self.files_regex_scanned += 1
            return names

        try:
            text = Path(key).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            self.files_regex_scanned += 1
            return []
        names = tier0_regex_module_names(text)
        self._note_regex_modules(key, names)
        self._save_regex_sidecar(key, names)
        self.files_regex_scanned += 1
        return names

    def _ensure_regex_candidates(self, module_name: str) -> List[str]:
        if module_name in self._prefer_file:
            preferred = self._prefer_file[module_name]
            rest = [f for f in self._module_to_files.get(module_name, []) if f != preferred]
            if preferred not in rest and preferred in self._module_to_files.get(module_name, []):
                return [preferred] + rest
            if module_name in self._module_to_files:
                return list(self._module_to_files[module_name])

        if not self._regex_queue:
            self._regex_queue = [s for s in self._sources if s not in self._regex_scanned]

        while module_name not in self._module_to_files and self._regex_queue:
            nxt = self._regex_queue.pop(0)
            self._tier0_scan_file(nxt)

        if module_name not in self._module_to_files:
            while self._regex_queue:
                nxt = self._regex_queue.pop(0)
                self._tier0_scan_file(nxt)
                if module_name in self._module_to_files:
                    break
            for src in self._sources:
                if src not in self._regex_scanned:
                    self._tier0_scan_file(src)
                if module_name in self._module_to_files:
                    break

        files = list(self._module_to_files.get(module_name, []))
        preferred = self._prefer_file.get(module_name)
        if preferred and preferred in files:
            files = [preferred] + [f for f in files if f != preferred]
        return files

    def tier1_scan_file(self, path: str) -> Dict[str, ModuleRecord]:
        """Light preprocess + instance scan for one translation unit."""
        key = str(Path(path).resolve())
        mem = self._validated_memory.get(key)
        if mem is not None:
            return mem

        disk = self._load_validated_sidecar(key)
        if disk is not None:
            self.cache_validated_hits += 1
            self._validated_memory[key] = disk
            self.files_validated += 1
            return disk

        from scan_inst.preprocess import preprocess_file_for_index

        defs: Dict[str, str] = dict(self._defines)
        text = preprocess_file_for_index(
            Path(key),
            self._include_dirs,
            defs,
            set(),
            skip_path_patterns=self._skip,
        )
        per_file = scan_preprocessed(text, key)
        out = {name: _record_lite(rec) for name, rec in per_file.items()}
        self._validated_memory[key] = out
        self._save_validated_sidecar(key, out)
        self.files_validated += 1
        for name in out:
            self._note_regex_modules(key, [name])
        return out

    def _edge_matches(
        self,
        edges: Sequence[InstanceEdge],
        inst_leaf: str,
        param_map: Mapping[str, str],
    ) -> Optional[InstanceEdge]:
        for edge in edges:
            if edge.inst_name == inst_leaf:
                return edge
            expanded = expand_inst_names(edge.inst_name, "", param_map)
            if inst_leaf in expanded:
                return edge
        return None

    def _apply_file_modules(self, path: str, modules: Mapping[str, ModuleRecord]) -> None:
        self._index.patch_files(
            [path],
            [],
            include_dirs=[str(p) for p in self._include_dirs],
            defines=self._defines,
            jobs=1,
        )

    def ensure_module_in_index(
        self,
        module_name: str,
        *,
        expect_inst: Optional[Tuple[str, str]] = None,
    ) -> bool:
        """
        Load *module_name* into the shared index from the best candidate file.

        When *expect_inst* is ``(parent_module, inst_leaf)``, prefer a file whose
        scanned parent body contains that instance edge.
        """
        rec = self._index.get_module(module_name)
        if rec is not None and rec.file_path:
            if expect_inst is None:
                return True
            parent_mod, inst_leaf = expect_inst
            if parent_mod == module_name:
                pmap = resolve_param_map(rec.raw_params)
                if self._edge_matches(
                    self._index.instances_for(module_name, {}, {}),
                    inst_leaf,
                    pmap,
                ):
                    return True

        candidates = self._ensure_regex_candidates(module_name)
        current = str(Path(rec.file_path).resolve()) if rec and rec.file_path else ""
        ordered = candidates
        if current:
            ordered = [f for f in candidates if f != current] + ([current] if current in candidates else [])

        for fpath in ordered:
            modules = self.tier1_scan_file(fpath)
            hit = modules.get(module_name)
            if hit is None:
                continue
            if expect_inst is not None:
                parent_mod, inst_leaf = expect_inst
                if parent_mod == module_name:
                    pmap = resolve_param_map(hit.raw_params)
                    if not self._edge_matches(hit.instances, inst_leaf, pmap):
                        continue
            self._apply_file_modules(fpath, modules)
            self._prefer_file[module_name] = fpath
            return self._index.get_module(module_name) is not None

        return self._index.get_module(module_name) is not None

    def resolve_child_edge(
        self,
        parent_module: str,
        parent_ctx: Mapping[str, str],
        inst_leaf: str,
        *,
        current_file: str = "",
    ) -> Optional[InstanceEdge]:
        """Tier-1 confirmed child edge, trying alternate decl files on miss."""
        rec = self._index.get_module(parent_module)
        if rec is not None:
            pmap = resolve_param_map(rec.raw_params, parent=parent_ctx)
            edge = self._edge_matches(
                self._index.instances_for(parent_module, parent_ctx, {}),
                inst_leaf,
                pmap,
            )
            if edge is not None:
                if rec.file_path:
                    self._prefer_file[parent_module] = str(Path(rec.file_path).resolve())
                return edge

        if self.ensure_module_in_index(
            parent_module,
            expect_inst=(parent_module, inst_leaf),
        ):
            rec = self._index.get_module(parent_module)
            if rec is not None:
                pmap = resolve_param_map(rec.raw_params, parent=parent_ctx)
                return self._edge_matches(
                    self._index.instances_for(parent_module, parent_ctx, {}),
                    inst_leaf,
                    pmap,
                )

        if current_file:
            cur = str(Path(current_file).resolve())
            for fpath in self._ensure_regex_candidates(parent_module):
                if fpath == cur:
                    continue
                modules = self.tier1_scan_file(fpath)
                hit = modules.get(parent_module)
                if hit is None:
                    continue
                pmap = resolve_param_map(hit.raw_params, parent=parent_ctx)
                edge = self._edge_matches(hit.instances, inst_leaf, pmap)
                if edge is not None:
                    self._apply_file_modules(fpath, modules)
                    self._prefer_file[parent_module] = fpath
                    return edge
        return None

    def find_module_decl_file(self, module_name: str) -> Optional[str]:
        files = self._ensure_regex_candidates(module_name)
        if not files:
            return None
        preferred = self._prefer_file.get(module_name)
        if preferred and preferred in files:
            return preferred
        return files[0]