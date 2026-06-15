"""Pre-built module/file index for fast hierarchy elaboration."""

from __future__ import annotations

import fnmatch
import os
import re
from collections import defaultdict
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from typing import Callable, Dict, List, Literal, Mapping, Optional, Sequence, Tuple

from scan_inst.generate_fold import needs_generate_fold, prepare_body_for_instance_scan
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
    folded = prepare_body_for_instance_scan(body, pmap)
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


def _preprocess_scan_file_task(
    item: Tuple[str, Tuple[str, ...], Tuple[Tuple[str, str], ...], ScanMode],
) -> Dict[str, ModuleRecord]:
    """Picklable fused preprocess + scan (avoids retaining full preprocessed text)."""
    fpath, inc_dirs, define_items, mode = item
    path = Path(fpath)
    if mode == "ignore":
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            text = ""
        return scan_ignore_path_stubs(text, fpath)
    from scan_inst.preprocess import preprocess_file

    inc = [Path(p) for p in inc_dirs]
    defs: Dict[str, str] = dict(define_items)
    text = preprocess_file(path, inc, defs, set())
    return scan_preprocessed(text, fpath)


def _merge_file_scans(
    merged: Dict[str, ModuleRecord],
    per_file: Dict[str, ModuleRecord],
) -> None:
    for name, rec in per_file.items():
        if name not in merged:
            merged[name] = rec


def _preprocessed_text(preprocessed: Mapping[str, str], fpath: str) -> str:
    for key in (fpath, str(Path(fpath)), str(Path(fpath).resolve())):
        hit = preprocessed.get(key)
        if hit is not None:
            return hit
    raise KeyError(fpath)


def _build_merged_from_sources(
    parse_sources: List[str],
    ignore_sources: List[str],
    *,
    include_dirs: Sequence[str],
    defines: Mapping[str, str],
    jobs: int = 0,
    low_memory: bool = False,
    on_progress: Optional[Callable[[str], None]] = None,
    file_via_filelist: Optional[Mapping[str, str]] = None,
) -> Dict[str, ModuleRecord]:
    """Default: parallel preprocess then in-memory scan (preprocessed map discarded)."""
    if low_memory:
        return _scan_sources_fused(
            parse_sources,
            ignore_sources,
            include_dirs=include_dirs,
            defines=defines,
            jobs=jobs,
            on_progress=on_progress,
            file_via_filelist=file_via_filelist,
        )
    from scan_inst.preprocess import preprocess_sources

    all_sources = list(parse_sources) + list(ignore_sources)
    preprocessed = preprocess_sources(
        all_sources,
        include_dirs,
        defines,
        jobs=jobs,
        on_progress=on_progress,
        file_via_filelist=file_via_filelist,
    )
    return _scan_sources(
        preprocessed,
        parse_sources,
        ignore_sources,
        jobs=jobs,
        on_progress=on_progress,
        file_via_filelist=file_via_filelist,
    )


def _scan_sources(
    preprocessed: Mapping[str, str],
    parse_sources: List[str],
    ignore_sources: List[str],
    *,
    jobs: int = 0,
    on_progress: Optional[Callable[[str], None]] = None,
    file_via_filelist: Optional[Mapping[str, str]] = None,
) -> Dict[str, ModuleRecord]:
    tasks: List[Tuple[str, str, ScanMode]] = [
        (fpath, _preprocessed_text(preprocessed, fpath), "parse")
        for fpath in parse_sources
    ] + [
        (fpath, _preprocessed_text(preprocessed, fpath), "ignore")
        for fpath in ignore_sources
    ]
    merged: Dict[str, ModuleRecord] = {}
    if not tasks:
        return merged

    total = len(tasks)
    if on_progress:
        on_progress(f"index: scanning 0/{total} files (in-process)")
    for i, task in enumerate(tasks, start=1):
        _merge_file_scans(merged, _scan_file_task(task))
        if on_progress and (i == total or i % 500 == 0):
            from scan_inst.progress import format_work_location

            loc = format_work_location(
                task[0],
                index=i,
                total=total,
                via_map=file_via_filelist,
            )
            on_progress(f"index: scanning {i}/{total} files — {loc}")
    return merged


def _scan_sources_fused(
    parse_sources: List[str],
    ignore_sources: List[str],
    *,
    include_dirs: Sequence[str],
    defines: Mapping[str, str],
    jobs: int = 0,
    on_progress: Optional[Callable[[str], None]] = None,
    file_via_filelist: Optional[Mapping[str, str]] = None,
) -> Dict[str, ModuleRecord]:
    define_items = tuple(sorted(defines.items()))
    inc_dirs = tuple(str(Path(p)) for p in include_dirs)
    tasks: List[Tuple[str, Tuple[str, ...], Tuple[Tuple[str, str], ...], ScanMode]] = [
        (fpath, inc_dirs, define_items, "parse") for fpath in parse_sources
    ] + [
        (fpath, inc_dirs, define_items, "ignore") for fpath in ignore_sources
    ]
    merged: Dict[str, ModuleRecord] = {}
    if not tasks:
        return merged

    workers = _resolve_jobs(jobs, len(tasks))
    total = len(tasks)
    if on_progress:
        jobs_note = "auto" if jobs == 0 else str(jobs)
        on_progress(
            f"index: scanning 0/{total} files "
            f"({workers} workers, jobs={jobs_note})"
        )
    if workers == 1:
        for i, task in enumerate(tasks, start=1):
            _merge_file_scans(merged, _preprocess_scan_file_task(task))
            if on_progress and (i == total or i % 500 == 0):
                from scan_inst.progress import format_work_location

                loc = format_work_location(
                    task[0],
                    index=i,
                    total=total,
                    via_map=file_via_filelist,
                )
                on_progress(f"index: scanning {i}/{total} sources — {loc}")
        return merged

    try:
        from scan_inst.manifest import scan_chunksize

        chunk = scan_chunksize(total, workers)
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for i, per_file in enumerate(
                pool.map(_preprocess_scan_file_task, tasks, chunksize=chunk),
                start=1,
            ):
                _merge_file_scans(merged, per_file)
                if on_progress and (i == total or i % 500 == 0):
                    from scan_inst.progress import format_work_location

                    fpath = tasks[i - 1][0]
                    loc = format_work_location(
                        fpath,
                        index=i,
                        total=total,
                        via_map=file_via_filelist,
                    )
                    on_progress(f"index: scanning {i}/{total} sources — {loc}")
    except (OSError, PermissionError, RuntimeError):
        for task in tasks:
            _merge_file_scans(merged, _preprocess_scan_file_task(task))
    return merged


def _scan_instances_for_index(
    body: str,
    raw_params: Mapping[str, str],
) -> Tuple[List[InstanceEdge], bool]:
    """Index-time scan: defer generate fold to :meth:`DesignIndex.instances_for`."""
    defer = needs_generate_fold(body)
    if defer:
        return [], True
    pmap = resolve_param_map(raw_params)
    return scan_hierarchy_instances(body, param_map=pmap), False


def scan_preprocessed(text: str, file_path: str) -> Dict[str, ModuleRecord]:
    out: Dict[str, ModuleRecord] = {}
    for m in _MODULE_BLOCK_RE.finditer(text):
        name = m.group(1)
        chunk = m.group(2)
        header, body = split_module_header(chunk)
        raw_params = collect_module_params(header, body)
        edges, defer_fold = _scan_instances_for_index(body, raw_params)
        kind_m = re.search(
            rf"\b(module|interface|program)\s+{re.escape(name)}\b",
            text[m.start() : m.start() + 80],
            re.IGNORECASE,
        )
        is_interface = bool(kind_m and kind_m.group(1).lower() == "interface")
        out[name] = ModuleRecord(
            module_name=name,
            file_path=file_path,
            body="",
            raw_params=dict(raw_params),
            instances=edges,
            needs_generate_fold=defer_fold,
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
        preprocess_include_dirs: Optional[Sequence[str]] = None,
        preprocess_defines: Optional[Mapping[str, str]] = None,
        preprocessed_sources: Optional[Mapping[str, str]] = None,
        low_memory: bool = False,
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
        self._preprocess_include_dirs: List[str] = [
            str(Path(p)) for p in (preprocess_include_dirs or ())
        ]
        self._preprocess_defines: Dict[str, str] = dict(preprocess_defines or {})
        self._preprocessed_sources: Dict[str, str] = {
            str(Path(k)): v for k, v in (preprocessed_sources or {}).items()
        }
        self.low_memory: bool = low_memory
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
            if rec.needs_generate_fold:
                continue
            if rec.raw_params or rec.instances:
                self._default_ctx[name] = _ctx_key(resolve_param_map(rec.raw_params))

    def _rebuild_file_modules(self) -> None:
        self.file_modules = defaultdict(list)
        for name, rec in self.modules.items():
            self.file_modules[rec.file_path].append(name)
        for names in self.file_modules.values():
            names.sort()

    def _source_text(self, file_path: str) -> str:
        keys = (file_path, str(Path(file_path)), str(Path(file_path).resolve()))
        for key in keys:
            hit = self._preprocessed_sources.get(key)
            if hit is not None:
                return hit
        path = Path(file_path)
        if not path.is_file():
            return ""
        if self._preprocess_include_dirs or self._preprocess_defines:
            from scan_inst.preprocess import preprocess_file

            inc = [Path(p) for p in self._preprocess_include_dirs]
            return preprocess_file(path, inc, self._preprocess_defines, set())
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return ""

    def module_body(self, mod_name: str) -> str:
        rec = self.modules.get(mod_name)
        if not rec or rec.stop_reason or rec.is_blackbox:
            return ""
        if rec.body:
            return rec.body
        text = self._source_text(rec.file_path)
        if not text:
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
        self._preprocessed_sources.clear()
        self._instance_cache.clear()

    def patch_files(
        self,
        changed_files: Sequence[str],
        removed_files: Sequence[str],
        *,
        include_dirs: Sequence[str] = (),
        defines: Mapping[str, str] | None = None,
        jobs: int = 0,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> None:
        if include_dirs:
            self._preprocess_include_dirs = [str(Path(p)) for p in include_dirs]
        if defines is not None:
            self._preprocess_defines = dict(defines)
        removed = set(removed_files)
        touched = set(changed_files) | removed
        for name in list(self.modules):
            if self.modules[name].file_path in touched:
                del self.modules[name]
        parse_sources = list(changed_files)
        if parse_sources:
            merged = _build_merged_from_sources(
                parse_sources,
                [],
                include_dirs=include_dirs,
                defines=defines or {},
                jobs=jobs,
                low_memory=self.low_memory,
                on_progress=on_progress,
                file_via_filelist=self.file_via_filelist,
            )
            for name, rec in merged.items():
                self.modules[name] = rec
        self._rebuild_file_modules()
        self._instance_cache.clear()
        self._rebuild_default_ctx()

    @classmethod
    def _assemble(
        cls,
        merged: Dict[str, ModuleRecord],
        *,
        path_patterns: List[str],
        module_patterns: List[str],
        library_files: Optional[List[str]] = None,
        library_dirs: Optional[List[str]] = None,
        libexts: Optional[List[str]] = None,
        file_via_filelist: Optional[Mapping[str, str]] = None,
        file_filelist_chain: Optional[Mapping[str, str]] = None,
        filelist_info: Optional[Mapping[str, FilelistLinkInfo]] = None,
        filelist_children: Optional[Mapping[str, List[str]]] = None,
        filelist_edges: Optional[List[tuple[str, str, str]]] = None,
        index_jobs: int = 1,
        preprocess_include_dirs: Optional[Sequence[str]] = None,
        preprocess_defines: Optional[Mapping[str, str]] = None,
        preprocessed_sources: Optional[Mapping[str, str]] = None,
        low_memory: bool = False,
    ) -> "DesignIndex":
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
            preprocess_include_dirs=preprocess_include_dirs,
            preprocess_defines=preprocess_defines,
            preprocessed_sources=preprocessed_sources,
            low_memory=low_memory,
        )
        index.index_jobs = index_jobs
        return index

    @classmethod
    def build_from_sources(
        cls,
        sources: Sequence[str],
        *,
        include_dirs: Sequence[str],
        defines: Mapping[str, str],
        library_files: Optional[List[str]] = None,
        library_dirs: Optional[List[str]] = None,
        libexts: Optional[List[str]] = None,
        ignore_paths: Optional[List[str]] = None,
        ignore_path_files: Optional[List[str]] = None,
        ignore_modules: Optional[List[str]] = None,
        jobs: int = 0,
        low_memory: bool = False,
        on_progress: Optional[Callable[[str], None]] = None,
        file_via_filelist: Optional[Mapping[str, str]] = None,
        file_filelist_chain: Optional[Mapping[str, str]] = None,
        filelist_info: Optional[Mapping[str, FilelistLinkInfo]] = None,
        filelist_children: Optional[Mapping[str, List[str]]] = None,
        filelist_edges: Optional[List[tuple[str, str, str]]] = None,
    ) -> "DesignIndex":
        path_patterns, module_patterns = resolve_ignore_path_patterns(
            ignore_paths or (),
            ignore_path_files=ignore_path_files or (),
            ignore_modules=ignore_modules or (),
        )
        src_list = sorted(str(Path(s)) for s in sources)
        parse_sources, ignore_sources = partition_sources(src_list, path_patterns)
        merged = _build_merged_from_sources(
            parse_sources,
            ignore_sources,
            include_dirs=include_dirs,
            defines=defines,
            jobs=jobs,
            low_memory=low_memory,
            on_progress=on_progress,
            file_via_filelist=file_via_filelist,
        )
        return cls._assemble(
            merged,
            path_patterns=path_patterns,
            module_patterns=module_patterns,
            library_files=library_files,
            library_dirs=library_dirs,
            libexts=libexts,
            file_via_filelist=file_via_filelist,
            file_filelist_chain=file_filelist_chain,
            filelist_info=filelist_info,
            filelist_children=filelist_children,
            filelist_edges=filelist_edges,
            index_jobs=_resolve_jobs(jobs, len(parse_sources) + len(ignore_sources)),
            preprocess_include_dirs=include_dirs,
            preprocess_defines=defines,
            low_memory=low_memory,
        )

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
        return cls._assemble(
            merged,
            path_patterns=path_patterns,
            module_patterns=module_patterns,
            library_files=library_files,
            library_dirs=library_dirs,
            libexts=libexts,
            file_via_filelist=file_via_filelist,
            file_filelist_chain=file_filelist_chain,
            filelist_info=filelist_info,
            filelist_children=filelist_children,
            filelist_edges=filelist_edges,
            index_jobs=_resolve_jobs(jobs, len(parse_sources) + len(ignore_sources)),
            preprocessed_sources=preprocessed,
        )

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

        if (
            not rec.needs_generate_fold
            and not overrides
            and not parent_ctx
        ):
            return list(rec.instances)

        if not overrides and not rec.needs_generate_fold:
            pmap = resolve_param_map(
                rec.raw_params,
                overrides=overrides,
                parent=parent_ctx,
            )
            if _ctx_key(pmap) == self._default_ctx.get(mod_name):
                return rec.instances

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