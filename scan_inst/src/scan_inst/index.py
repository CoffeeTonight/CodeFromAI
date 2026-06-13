"""Pre-built module/file index for fast hierarchy elaboration."""

from __future__ import annotations

import fnmatch
import os
import re
from collections import defaultdict
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from typing import Callable, Dict, List, Literal, Mapping, Optional, Tuple

from scan_inst.generate_fold import fold_generate_regions
from scan_inst.inst_scan import (
    _MODULE_BLOCK_RE,
    scan_hierarchy_instances,
)
from scan_inst.ignore_path import (
    partition_sources,
    resolve_ignore_path_patterns,
    scan_ignore_path_stubs,
    source_path_matches,
)
from scan_inst.library_scan import scan_library_modules
from scan_inst.models import FilelistLinkInfo, InstanceEdge, ModuleRecord
from scan_inst.params import (
    collect_module_params,
    resolve_param_map,
    split_module_header,
)


def _scan_module_body(
    body: str,
    raw_params: Mapping[str, str],
    *,
    parent_ctx: Optional[Mapping[str, str]] = None,
    overrides: Optional[Mapping[str, str]] = None,
) -> List[InstanceEdge]:
    pmap = resolve_param_map(raw_params, overrides=overrides, parent=parent_ctx)
    folded = fold_generate_regions(body, pmap)
    return scan_hierarchy_instances(folded, param_map=pmap)


def _ctx_key(pmap: Mapping[str, str]) -> str:
    return "|".join(f"{k}={v}" for k, v in sorted(pmap.items()))


def _module_name_ignored(name: str, patterns: List[str]) -> bool:
    for pat in patterns:
        if not pat:
            continue
        if any(ch in pat for ch in ("*", "?", "[")):
            if fnmatch.fnmatchcase(name, pat):
                return True
        elif pat == name:
            return True
    return False


ScanMode = Literal["parse", "ignore"]


def _resolve_jobs(jobs: int, num_tasks: int) -> int:
    if jobs < 0:
        return 1
    if jobs == 0:
        cpu = os.cpu_count() or 1
        return max(1, min(cpu, num_tasks))
    return max(1, min(jobs, num_tasks))


def _scan_file_task(item: Tuple[str, str, ScanMode]) -> Dict[str, ModuleRecord]:
    """Picklable per-file scan (file-module table row)."""
    fpath, text, mode = item
    if mode == "ignore":
        return scan_ignore_path_stubs(text, fpath)
    return scan_preprocessed(text, fpath)


def _merge_file_scans(
    merged: Dict[str, ModuleRecord],
    per_file: Dict[str, ModuleRecord],
) -> None:
    for name, rec in per_file.items():
        if name not in merged:
            merged[name] = rec


def _scan_sources(
    preprocessed: Mapping[str, str],
    parse_sources: List[str],
    ignore_sources: List[str],
    *,
    jobs: int = 0,
    on_progress: Optional[Callable[[str], None]] = None,
) -> Dict[str, ModuleRecord]:
    tasks: List[Tuple[str, str, ScanMode]] = [
        (fpath, preprocessed[fpath], "parse") for fpath in parse_sources
    ] + [
        (fpath, preprocessed[fpath], "ignore") for fpath in ignore_sources
    ]
    merged: Dict[str, ModuleRecord] = {}
    if not tasks:
        return merged

    workers = _resolve_jobs(jobs, len(tasks))
    total = len(tasks)
    if on_progress:
        on_progress(f"index: scanning 0/{total} files ({workers} workers)")
    if workers == 1:
        for i, task in enumerate(tasks, start=1):
            _merge_file_scans(merged, _scan_file_task(task))
            if on_progress and (i == total or i % 500 == 0):
                on_progress(f"index: scanning {i}/{total} files")
        return merged

    try:
        from scan_inst.manifest import scan_chunksize

        chunk = scan_chunksize(total, workers)
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for i, per_file in enumerate(
                pool.map(_scan_file_task, tasks, chunksize=chunk),
                start=1,
            ):
                _merge_file_scans(merged, per_file)
                if on_progress and (i == total or i % 500 == 0):
                    on_progress(f"index: scanning {i}/{total} files")
    except (OSError, PermissionError, RuntimeError):
        for task in tasks:
            _merge_file_scans(merged, _scan_file_task(task))
    return merged


def scan_preprocessed(text: str, file_path: str) -> Dict[str, ModuleRecord]:
    out: Dict[str, ModuleRecord] = {}
    for m in _MODULE_BLOCK_RE.finditer(text):
        name = m.group(1)
        chunk = m.group(2)
        header, body = split_module_header(chunk)
        raw_params = collect_module_params(header, body)
        edges = _scan_module_body(body, raw_params)
        kind_m = re.search(
            rf"\b(module|interface|program)\s+{re.escape(name)}\b",
            text[m.start() : m.start() + 80],
            re.IGNORECASE,
        )
        is_interface = bool(kind_m and kind_m.group(1).lower() == "interface")
        out[name] = ModuleRecord(
            module_name=name,
            file_path=file_path,
            body=body,
            raw_params=dict(raw_params),
            instances=edges,
            is_interface=is_interface,
        )
    return out


class DesignIndex:
    """
    File/module maps built once from RTL.

    Elaboration looks up ``modules[child_type]`` and reuses default instance
    lists; non-default parameter contexts are cached by ``(module, ctx_key)``.
    """

    def __init__(
        self,
        modules: Mapping[str, ModuleRecord],
        *,
        ignore_path_patterns: Optional[List[str]] = None,
        ignore_module_patterns: Optional[List[str]] = None,
        file_via_filelist: Optional[Mapping[str, str]] = None,
        file_filelist_chain: Optional[Mapping[str, str]] = None,
        filelist_info: Optional[Mapping[str, FilelistLinkInfo]] = None,
        filelist_children: Optional[Mapping[str, List[str]]] = None,
        filelist_edges: Optional[List[tuple[str, str, str]]] = None,
    ) -> None:
        self.modules: Dict[str, ModuleRecord] = dict(modules)
        self.ignore_path_patterns: List[str] = list(ignore_path_patterns or [])
        self.ignore_module_patterns: List[str] = list(ignore_module_patterns or [])
        self.file_via_filelist: Dict[str, str] = dict(file_via_filelist or {})
        self.file_filelist_chain: Dict[str, str] = dict(file_filelist_chain or {})
        self.filelist_info: Dict[str, FilelistLinkInfo] = dict(filelist_info or {})
        self.filelist_children: Dict[str, List[str]] = {
            k: list(v) for k, v in (filelist_children or {}).items()
        }
        self.filelist_edges: List[tuple[str, str, str]] = list(filelist_edges or [])
        self.index_jobs: int = 1
        self.file_modules: Dict[str, List[str]] = defaultdict(list)
        for name, rec in self.modules.items():
            self.file_modules[rec.file_path].append(name)
        for names in self.file_modules.values():
            names.sort()
        self._default_ctx: Dict[str, str] = {}
        self._instance_cache: Dict[Tuple[str, str], List[InstanceEdge]] = {}
        self._rebuild_default_ctx()

    def _rebuild_default_ctx(self) -> None:
        self._default_ctx = {}
        for name, rec in self.modules.items():
            if rec.raw_params or rec.instances:
                self._default_ctx[name] = _ctx_key(resolve_param_map(rec.raw_params))

    def _rebuild_file_modules(self) -> None:
        self.file_modules = defaultdict(list)
        for name, rec in self.modules.items():
            self.file_modules[rec.file_path].append(name)
        for names in self.file_modules.values():
            names.sort()

    def module_body(self, mod_name: str) -> str:
        rec = self.modules.get(mod_name)
        if not rec or rec.stop_reason or rec.is_blackbox:
            return ""
        if rec.body:
            return rec.body
        path = Path(rec.file_path)
        if not path.is_file():
            return ""
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return ""
        for m in _MODULE_BLOCK_RE.finditer(text):
            if m.group(1) != mod_name:
                continue
            _header, body = split_module_header(m.group(2))
            rec.body = body
            return body
        return ""

    def strip_bodies_for_cache(self) -> None:
        for rec in self.modules.values():
            rec.body = ""
        self._instance_cache.clear()

    def patch_files(
        self,
        preprocessed: Mapping[str, str],
        changed_files: Sequence[str],
        removed_files: Sequence[str],
        *,
        jobs: int = 0,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> None:
        removed = set(removed_files)
        touched = set(changed_files) | removed
        for name in list(self.modules):
            if self.modules[name].file_path in touched:
                del self.modules[name]
        parse_sources = [f for f in changed_files if f in preprocessed]
        if parse_sources:
            merged = _scan_sources(
                preprocessed,
                parse_sources,
                [],
                jobs=jobs,
                on_progress=on_progress,
            )
            for name, rec in merged.items():
                self.modules[name] = rec
        self._rebuild_file_modules()
        self._instance_cache.clear()
        self._rebuild_default_ctx()

    @classmethod
    def build(
        cls,
        preprocessed: Mapping[str, str],
        *,
        library_files: Optional[List[str]] = None,
        library_dirs: Optional[List[str]] = None,
        libexts: Optional[List[str]] = None,
        ignore_paths: Optional[List[str]] = None,
        ignore_path_files: Optional[List[str]] = None,
        ignore_modules: Optional[List[str]] = None,
        jobs: int = 0,
        on_progress: Optional[Callable[[str], None]] = None,
        file_via_filelist: Optional[Mapping[str, str]] = None,
        file_filelist_chain: Optional[Mapping[str, str]] = None,
        filelist_info: Optional[Mapping[str, FilelistLinkInfo]] = None,
        filelist_children: Optional[Mapping[str, List[str]]] = None,
        filelist_edges: Optional[List[tuple[str, str, str]]] = None,
    ) -> DesignIndex:
        path_patterns, module_patterns = resolve_ignore_path_patterns(
            ignore_paths or (),
            ignore_path_files=ignore_path_files or (),
            ignore_modules=ignore_modules or (),
        )
        sources = sorted(preprocessed.keys())
        parse_sources, ignore_sources = partition_sources(sources, path_patterns)
        merged = _scan_sources(
            preprocessed,
            parse_sources,
            ignore_sources,
            jobs=jobs,
            on_progress=on_progress,
        )
        for name, rec in list(merged.items()):
            if rec.stop_reason:
                continue
            if source_path_matches(rec.file_path, path_patterns):
                merged[name] = ModuleRecord(
                    module_name=rec.module_name,
                    file_path=rec.file_path,
                    stop_reason="ignorePath",
                )
                continue
            if _module_name_ignored(name, module_patterns):
                merged[name] = ModuleRecord(
                    module_name=rec.module_name,
                    file_path=rec.file_path,
                    stop_reason="ignorePath",
                )
        if library_files is not None or library_dirs is not None:
            stubs = scan_library_modules(
                library_files or [],
                library_dirs or [],
                libexts=libexts or (),
            )
            for name, stub in stubs.items():
                if name not in merged:
                    merged[name] = ModuleRecord(
                        module_name=stub.module_name,
                        file_path=stub.file_path,
                        is_blackbox=True,
                        stop_reason="ignorePath",
                    )
        index = cls(
            merged,
            ignore_path_patterns=path_patterns,
            ignore_module_patterns=module_patterns,
            file_via_filelist=file_via_filelist,
            file_filelist_chain=file_filelist_chain,
            filelist_info=filelist_info,
            filelist_children=filelist_children,
            filelist_edges=filelist_edges,
        )
        index.index_jobs = _resolve_jobs(
            jobs,
            len(parse_sources) + len(ignore_sources),
        )
        return index

    def get_module(self, name: str) -> Optional[ModuleRecord]:
        return self.modules.get(name)

    def filelist_for(self, rtl_file: str) -> str:
        key = str(Path(rtl_file).resolve()) if rtl_file else ""
        return self.file_via_filelist.get(key, "")

    def filelist_chain_for(self, rtl_file: str) -> str:
        key = str(Path(rtl_file).resolve()) if rtl_file else ""
        return self.file_filelist_chain.get(key, "")

    def module_stop_reason(self, mod_name: str) -> str:
        rec = self.modules.get(mod_name)
        if rec is None:
            return "unknown"
        if rec.stop_reason:
            return rec.stop_reason
        if _module_name_ignored(mod_name, self.ignore_module_patterns):
            return "ignorePath"
        if rec.is_blackbox:
            return "ignorePath"
        return ""

    def instances_for(
        self,
        mod_name: str,
        parent_ctx: Mapping[str, str],
        overrides: Mapping[str, str],
    ) -> List[InstanceEdge]:
        rec = self.modules.get(mod_name)
        if not rec:
            return []
        if rec.stop_reason or rec.is_blackbox:
            return list(rec.instances)

        body = self.module_body(mod_name)
        if not body and rec.instances:
            return list(rec.instances)

        pmap = resolve_param_map(
            rec.raw_params,
            overrides=overrides,
            parent=parent_ctx,
        )
        ctx_key = _ctx_key(pmap)
        if not overrides and ctx_key == self._default_ctx.get(mod_name):
            return rec.instances

        cache_key = (mod_name, ctx_key)
        cached = self._instance_cache.get(cache_key)
        if cached is not None:
            return cached

        edges = _scan_module_body(
            body,
            rec.raw_params,
            parent_ctx=parent_ctx,
            overrides=overrides,
        )
        self._instance_cache[cache_key] = edges
        return edges