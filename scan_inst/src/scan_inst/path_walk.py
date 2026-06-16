"""
Path-walk connect mode: build only RTL on endpoint instance chains + LCA subtrees.

Reuses :class:`DesignIndex`, :func:`elaborate` helpers, and
:class:`ConnectivitySession` without a full filelist index scan.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from scan_inst.connect_endpoints import _lca, resolve_endpoint
from scan_inst.connect_request import ConnectivityRequest
from scan_inst.connectivity import ConnectivityBatchResult, ConnectivitySession
from scan_inst.filelist import FilelistResult
from scan_inst.ignore_path import resolve_ignore_path_patterns, source_path_matches
from scan_inst.index import DesignIndex
from scan_inst.inst_scan import expand_inst_names
from scan_inst.lazy_scope import endpoint_specs_from_request, hierarchy_prefixes
from scan_inst.library_scan import scan_library_modules
from scan_inst.models import FlatRow, InstanceEdge
from scan_inst.params import resolve_param_map
from scan_inst.top_find import resolve_top_modules

_MODULE_DEF_RE = re.compile(
    r"^\s*(?:module|interface|program)\s+([A-Za-z_]\w*)",
    re.MULTILINE | re.IGNORECASE,
)


@dataclass
class PathWalkStats:
    modules_loaded: int = 0
    files_scanned: int = 0
    paths_walked: int = 0
    subtrees_expanded: int = 0
    checks_run: int = 0


class ModuleFileResolver:
    """Lazy module name → defining RTL file (filelist sources only)."""

    def __init__(
        self,
        sources: Sequence[str | Path],
        *,
        skip_path_patterns: Sequence[str] = (),
    ) -> None:
        self._sources = [str(Path(s).resolve()) for s in sources]
        self._skip = tuple(skip_path_patterns)
        self._module_to_file: Dict[str, str] = {}
        self._scanned_files: Set[str] = set()

    @property
    def files_scanned(self) -> int:
        return len(self._scanned_files)

    def remember(self, module_name: str, file_path: str) -> None:
        if module_name and file_path:
            self._module_to_file.setdefault(module_name, str(Path(file_path).resolve()))

    def seed_index(self, index: DesignIndex) -> None:
        for name, rec in index.modules.items():
            if rec.file_path:
                self.remember(name, rec.file_path)

    def _scan_file(self, path: str) -> None:
        if path in self._scanned_files:
            return
        self._scanned_files.add(path)
        if self._skip and source_path_matches(path, self._skip):
            return
        try:
            text = Path(path).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return
        for m in _MODULE_DEF_RE.finditer(text):
            self._module_to_file.setdefault(m.group(1), path)

    def find_file(self, module_name: str) -> Optional[str]:
        hit = self._module_to_file.get(module_name)
        if hit is not None:
            return hit
        for src in self._sources:
            if src in self._scanned_files:
                continue
            self._scan_file(src)
            hit = self._module_to_file.get(module_name)
            if hit is not None:
                return hit
        return self._module_to_file.get(module_name)


@dataclass
class PathWalkState:
    """Incremental hierarchy rows built by walking endpoint paths."""

    index: DesignIndex
    top: str
    resolver: ModuleFileResolver
    rows_by_path: Dict[str, FlatRow] = field(default_factory=dict)
    stats: PathWalkStats = field(default_factory=PathWalkStats)

    def rows(self) -> List[FlatRow]:
        return list(self.rows_by_path.values())

    def _add_row(
        self,
        mod: str,
        path: str,
        depth: int,
        parent: Optional[str],
        *,
        file_path: str,
        stop_reason: str,
        param_ctx: Mapping[str, str],
    ) -> None:
        if path in self.rows_by_path:
            return
        self.rows_by_path[path] = FlatRow(
            full_path=path,
            inst_leaf=path.rsplit(".", 1)[-1],
            module=mod,
            depth=depth,
            parent_path=parent,
            file=file_path,
            stop_reason=stop_reason,
            via_filelist=self.index.filelist_for(file_path),
            filelist_chain=self.index.filelist_chain_for(file_path),
            param_ctx=dict(param_ctx),
        )

    def ensure_root(self) -> None:
        if self.top in self.rows_by_path:
            return
        rec = self.index.get_module(self.top)
        if rec is None:
            raise ValueError(f"top module not in index: {self.top}")
        stop = self.index.module_stop_reason(self.top)
        self._add_row(
            self.top,
            self.top,
            0,
            None,
            file_path=rec.file_path,
            stop_reason=stop,
            param_ctx=resolve_param_map(rec.raw_params),
        )

    def _load_module(self, module_name: str) -> bool:
        if self.index.get_module(module_name) is not None:
            return True
        fpath = self.resolver.find_file(module_name)
        if not fpath:
            return False
        self.index.patch_files(
            [fpath],
            [],
            include_dirs=self.index._preprocess_include_dirs,
            defines=self.index._preprocess_defines,
            jobs=1,
        )
        self.resolver.seed_index(self.index)
        self.stats.modules_loaded += 1
        self.stats.files_scanned = self.resolver.files_scanned
        return self.index.get_module(module_name) is not None

    def _child_edge(self, parent_path: str, inst_leaf: str) -> Optional[InstanceEdge]:
        row = self.rows_by_path.get(parent_path)
        if row is None:
            return None
        rec = self.index.get_module(row.module)
        if rec is None:
            return None
        pmap = resolve_param_map(
            rec.raw_params,
            parent=row.param_ctx,
        )
        edges = self.index.instances_for(row.module, row.param_ctx, {})
        target = inst_leaf
        for edge in edges:
            if edge.inst_name == target:
                return edge
            expanded = expand_inst_names(edge.inst_name, "", pmap)
            if target in expanded:
                return edge
        return None

    def _attach_child(
        self,
        parent_path: str,
        inst_leaf: str,
        edge: InstanceEdge,
    ) -> Optional[str]:
        parent = self.rows_by_path.get(parent_path)
        if parent is None:
            return None
        child_path = f"{parent_path}.{inst_leaf}"
        if child_path in self.rows_by_path:
            return child_path
        if not self._load_module(edge.child_module):
            return None
        rec = self.index.get_module(edge.child_module)
        if rec is None:
            return None
        pmap = resolve_param_map(
            rec.raw_params,
            overrides=edge.param_overrides,
            parent=parent.param_ctx,
        )
        stop = self.index.module_stop_reason(edge.child_module)
        self._add_row(
            edge.child_module,
            child_path,
            parent.depth + 1,
            parent_path,
            file_path=rec.file_path,
            stop_reason=stop,
            param_ctx=pmap,
        )
        return child_path

    def ensure_path(self, instance_path: str) -> bool:
        """Walk ``top.u_child...`` loading RTL files on demand."""
        path = instance_path.strip()
        if not path or not path.startswith(self.top):
            return False
        if path in self.rows_by_path:
            return True
        self.ensure_root()
        parts = path.split(".")
        cur = parts[0]
        for seg in parts[1:]:
            nxt = f"{cur}.{seg}"
            if nxt in self.rows_by_path:
                cur = nxt
                continue
            edge = self._child_edge(cur, seg)
            if edge is None:
                return False
            attached = self._attach_child(cur, seg, edge)
            if attached is None:
                return False
            cur = attached
        self.stats.paths_walked += 1
        return path in self.rows_by_path

    def _expand_subtree(self, inst_path: str) -> None:
        row = self.rows_by_path.get(inst_path)
        if row is None or row.stop_reason:
            return
        rec = self.index.get_module(row.module)
        if rec is None:
            return
        edges = self.index.instances_for(row.module, row.param_ctx, {})
        for edge in edges:
            leaves = expand_inst_names(
                edge.inst_name,
                "",
                resolve_param_map(rec.raw_params, parent=row.param_ctx),
            )
            for leaf in leaves:
                child_path = f"{inst_path}.{leaf}"
                if child_path in self.rows_by_path:
                    self._expand_subtree(child_path)
                    continue
                hit = self._attach_child(inst_path, leaf, edge)
                if hit is not None:
                    self._expand_subtree(hit)

    def ensure_lca_subtree(self, path_a: str, path_b: str) -> None:
        """Ensure both endpoint chains exist; avoid expanding unrelated siblings."""
        lca = _lca(path_a, path_b)
        if not lca:
            return
        self.ensure_path(path_a)
        self.ensure_path(path_b)
        if lca not in self.rows_by_path:
            self.ensure_path(lca)
        self.stats.subtrees_expanded += 1


def _inst_path_from_spec(
    spec: str,
    state: PathWalkState,
) -> str:
    ep, _errors = resolve_endpoint(
        spec,
        state.rows(),
        state.index,
        top=state.top,
        require_port=False,
    )
    return ep.inst_path or spec.strip()


def _sorted_prefixes(specs: Sequence[str]) -> List[str]:
    prefixes = hierarchy_prefixes(specs)
    return sorted(prefixes, key=lambda p: (p.count("."), p))


def build_path_walk_state_from_specs(
    index: DesignIndex,
    top: str,
    specs: Sequence[str],
    resolver: ModuleFileResolver,
    *,
    expand_subtrees: Sequence[str] = (),
    on_progress: Optional[Callable[[str], None]] = None,
) -> PathWalkState:
    """Walk endpoint specs; optionally expand instance subtrees for cone / inst-trace."""
    state = PathWalkState(index=index, top=top, resolver=resolver)
    state.ensure_root()
    spec_list = [str(s).strip() for s in specs if str(s).strip()]
    if on_progress:
        on_progress(f"path-walk: {len(spec_list)} endpoint spec(s)")
    for prefix in _sorted_prefixes(spec_list):
        state.ensure_path(prefix)
    for spec in spec_list:
        inst = _inst_path_from_spec(spec, state)
        if inst:
            state.ensure_path(inst)
    for subtree_root in expand_subtrees:
        root = str(subtree_root).strip()
        if not root:
            continue
        if state.ensure_path(root):
            state._expand_subtree(root)
            state.stats.subtrees_expanded += 1
    return state


def build_path_walk_state(
    index: DesignIndex,
    top: str,
    request: ConnectivityRequest,
    resolver: ModuleFileResolver,
    *,
    on_progress: Optional[Callable[[str], None]] = None,
) -> PathWalkState:
    state = PathWalkState(index=index, top=top, resolver=resolver)
    state.ensure_root()
    specs = endpoint_specs_from_request(request)
    if on_progress:
        on_progress(f"path-walk: {len(specs)} endpoint spec(s)")
    for prefix in _sorted_prefixes(specs):
        state.ensure_path(prefix)
    seen_lca: Set[Tuple[str, str]] = set()
    for chk in request.checks:
        a = _inst_path_from_spec(chk.endpoint_a, state)
        b = _inst_path_from_spec(chk.endpoint_b, state)
        key = (a, b)
        if key in seen_lca:
            continue
        seen_lca.add(key)
        state.ensure_lca_subtree(a, b)
    return state


def run_path_walk_index(
    fl: FilelistResult,
    specs: Sequence[str],
    *,
    top: str = "",
    extra_defines: Mapping[str, str] | None = None,
    expand_subtrees: Sequence[str] = (),
    ignore_paths: Sequence[str] = (),
    ignore_path_files: Sequence[str] = (),
    ignore_modules: Sequence[str] = (),
    ignore_filelists: Sequence[str] = (),
    on_progress: Optional[Callable[[str], None]] = None,
) -> Tuple[DesignIndex, PathWalkState, str]:
    """On-demand index + hierarchy rows for arbitrary endpoint specs."""
    defines = dict(fl.defines)
    defines.update(extra_defines or {})
    index, resolver = create_path_walk_index(
        fl,
        top,
        defines=defines,
        ignore_paths=ignore_paths,
        ignore_path_files=ignore_path_files,
        ignore_modules=ignore_modules,
        ignore_filelists=ignore_filelists,
        on_progress=on_progress,
    )
    tops = resolve_top_modules(index, top=top, filelist_tops=fl.top_modules)
    top_name = tops[0]
    state = build_path_walk_state_from_specs(
        index,
        top_name,
        specs,
        resolver,
        on_progress=on_progress,
    )
    extra_roots = list(expand_subtrees)
    for spec in specs:
        inst = _inst_path_from_spec(spec, state)
        if inst and inst not in extra_roots:
            extra_roots.append(inst)
    for subtree_root in extra_roots:
        root = str(subtree_root).strip()
        if not root:
            continue
        if state.ensure_path(root):
            state._expand_subtree(root)
            state.stats.subtrees_expanded += 1
    if on_progress:
        on_progress(
            f"path-walk: {len(state.rows_by_path)} instance row(s), "
            f"{state.stats.modules_loaded} module(s) loaded"
        )
    return index, state, top_name


def create_path_walk_index(
    fl: FilelistResult,
    top: str,
    *,
    defines: Mapping[str, str],
    ignore_paths: Sequence[str] = (),
    ignore_path_files: Sequence[str] = (),
    ignore_modules: Sequence[str] = (),
    ignore_filelists: Sequence[str] = (),
    on_progress: Optional[Callable[[str], None]] = None,
) -> Tuple[DesignIndex, ModuleFileResolver]:
    path_patterns, module_patterns, filelist_patterns = resolve_ignore_path_patterns(
        ignore_paths,
        ignore_path_files=ignore_path_files,
        ignore_modules=ignore_modules,
        ignore_filelists=ignore_filelists,
    )
    stubs = scan_library_modules(
        [str(p) for p in fl.library_files],
        [str(p) for p in fl.library_dirs],
        libexts=fl.libexts,
        skip_path_patterns=path_patterns,
        jobs=1,
    )
    merged = dict(stubs)
    index = DesignIndex._assemble(
        merged,
        path_patterns=list(path_patterns),
        module_patterns=list(module_patterns),
        filelist_patterns=list(filelist_patterns),
        library_files=[str(p) for p in fl.library_files],
        library_dirs=[str(p) for p in fl.library_dirs],
        libexts=list(fl.libexts),
        file_via_filelist={
            str(Path(k).resolve()): v
            for k, v in (fl.source_via_filelist or {}).items()
        },
        file_filelist_chain={
            str(Path(k).resolve()): v
            for k, v in (fl.source_filelist_chain or {}).items()
        },
        preprocess_include_dirs=[str(p) for p in fl.include_dirs],
        preprocess_defines=dict(defines),
    )
    resolver = ModuleFileResolver(
        [str(p) for p in fl.source_files],
        skip_path_patterns=path_patterns,
    )
    resolver.seed_index(index)
    top_file = resolver.find_file(top)
    if not top_file:
        raise ValueError(f"top module {top!r} not found in filelist sources")
    if on_progress:
        on_progress(f"path-walk: seed top {top} ({Path(top_file).name})")
    index.patch_files(
        [top_file],
        [],
        include_dirs=[str(p) for p in fl.include_dirs],
        defines=dict(defines),
        jobs=1,
        on_progress=on_progress,
    )
    resolver.seed_index(index)
    return index, resolver


def run_path_walk_connect(
    request: ConnectivityRequest,
    fl: FilelistResult,
    *,
    top: str = "",
    extra_defines: Mapping[str, str] | None = None,
    ignore_paths: Sequence[str] = (),
    ignore_path_files: Sequence[str] = (),
    ignore_modules: Sequence[str] = (),
    ignore_filelists: Sequence[str] = (),
    on_progress: Optional[Callable[[str], None]] = None,
) -> Tuple[ConnectivityBatchResult, DesignIndex, PathWalkState]:
    """
    Path-walk batch connectivity: on-demand RTL + shared :class:`ConnectivitySession`.

    Uses ``jobs=1`` internally so ``mod_cache`` is shared across all checks.
    """
    defines = dict(fl.defines)
    defines.update(extra_defines or {})
    defines.update(request.defines)

    index, resolver = create_path_walk_index(
        fl,
        top,
        defines=defines,
        ignore_paths=ignore_paths,
        ignore_path_files=ignore_path_files,
        ignore_modules=ignore_modules,
        ignore_filelists=ignore_filelists,
        on_progress=on_progress,
    )
    tops = resolve_top_modules(index, top=top, filelist_tops=fl.top_modules)
    top_name = tops[0]

    state = build_path_walk_state(
        index,
        top_name,
        request,
        resolver,
        on_progress=on_progress,
    )
    if on_progress:
        on_progress(
            f"path-walk: {len(state.rows_by_path)} instance row(s), "
            f"{state.stats.modules_loaded} module(s) loaded"
        )

    session = ConnectivitySession(
        rows=state.rows(),
        index=index,
        top=top_name,
        defines=defines,
        strict_generate=request.strict_generate,
        ff_barrier=not request.include_ff,
        over_approximate_if=request.over_approximate_if,
    )
    batch = session.run_request(request, jobs=1)
    state.stats.checks_run = len(batch.results)
    return batch, index, state