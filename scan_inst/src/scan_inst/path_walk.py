"""
Path-walk connect mode: build only RTL on endpoint instance chains + LCA subtrees.

Reuses :class:`DesignIndex`, :func:`elaborate` helpers, and
:class:`ConnectivitySession` without a full filelist index scan.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Set, TextIO, Tuple

from scan_inst.connect_endpoints import _lca, resolve_endpoint
from scan_inst.connect_request import ConnectivityRequest
from scan_inst.connectivity import ConnectivityBatchResult, ConnectivitySession
from scan_inst.filelist import FilelistResult
from scan_inst.ignore_path import resolve_ignore_path_patterns, source_path_matches
from scan_inst.index import DesignIndex
from scan_inst.inst_scan import _read_hier_inst_path, expand_inst_names
from scan_inst.lazy_scope import endpoint_specs_from_request, hierarchy_prefixes
from scan_inst.library_scan import scan_library_modules
from scan_inst.models import FlatRow, InstanceEdge
from scan_inst.params import resolve_param_map
from scan_inst.hierarchy_log import (
    emit_path_walk_log,
    emit_path_walk_spine_log,
    format_path_walk_miss_line,
    open_path_walk_trace_log,
    path_walk_trace_show_message,
)
from scan_inst.path_walk_db import PathWalkModuleDb, path_walk_db_cache_key
from scan_inst.top_find import resolve_top_modules

_MODULE_DEF_RE = re.compile(
    r"^\s*(?:module|interface|program)\s+([A-Za-z_]\w*)",
    re.MULTILINE | re.IGNORECASE,
)


@dataclass(frozen=True)
class _PendingWalkMiss:
    parent_path: str
    inst_leaf: str
    reason: str
    target_path: str


@dataclass
class PathWalkStats:
    modules_loaded: int = 0
    files_scanned: int = 0
    files_regex_scanned: int = 0
    files_validated: int = 0
    cache_regex_hits: int = 0
    cache_validated_hits: int = 0
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
    mod_db: PathWalkModuleDb
    rows_by_path: Dict[str, FlatRow] = field(default_factory=dict)
    stats: PathWalkStats = field(default_factory=PathWalkStats)
    on_progress: Optional[Callable[[str], None]] = None
    trace_stream: Optional[TextIO] = None
    _trace_log: Optional[TextIO] = field(default=None, repr=False)
    _pending_misses: List[_PendingWalkMiss] = field(default_factory=list, repr=False)

    def _trace_streams(self) -> List[TextIO]:
        out: List[TextIO] = []
        if self.trace_stream is not None:
            out.append(self.trace_stream)
        if self._trace_log is not None:
            out.append(self._trace_log)
        return out

    def _walk_trace_enabled(self) -> bool:
        return bool(self._trace_streams()) or self.on_progress is not None

    def _emit_walk(self, message: str) -> None:
        if not message or not path_walk_trace_show_message(message):
            return
        streams = self._trace_streams()
        if streams:
            for stream in streams:
                emit_path_walk_log(message, stream=stream)
        elif self.on_progress is not None:
            self.on_progress(f"path-walk: {message}")

    def _emit_walk_spine(self, path: str, *, title: str) -> None:
        streams = self._trace_streams()
        if not streams:
            return
        for stream in streams:
            emit_path_walk_spine_log(
                path,
                self.rows_by_path,
                stream=stream,
                title=title,
            )

    def _emit_walk_node(self, path: str, *, action: str = "ok") -> None:
        row = self.rows_by_path.get(path)
        if row is None or not self._walk_trace_enabled():
            return
        message = f"{action} {path}  module={row.module}"
        if row.file:
            message += f"  rtl={row.file}"
        if row.via_filelist:
            message += f"  via_filelist={row.via_filelist}"
        if row.filelist_chain:
            message += f"  filelist_chain={row.filelist_chain}"
        if row.stop_reason:
            message += f"  stop={row.stop_reason}"
        self._emit_walk(message)

    def _clear_pending_misses(self, target_path: str) -> None:
        if not target_path:
            return
        self._pending_misses = [
            miss
            for miss in self._pending_misses
            if miss.target_path != target_path
        ]

    def _queue_walk_miss(
        self,
        parent_path: str,
        inst_leaf: str,
        *,
        reason: str,
        target_path: str,
    ) -> None:
        self._clear_pending_misses(target_path)
        self._pending_misses.append(
            _PendingWalkMiss(
                parent_path=parent_path,
                inst_leaf=inst_leaf,
                reason=reason,
                target_path=target_path,
            )
        )

    def _emit_walk_miss(
        self,
        parent_path: str,
        inst_leaf: str,
        *,
        reason: str,
        target_path: str = "",
    ) -> None:
        if not self._walk_trace_enabled():
            return
        parent = self.rows_by_path.get(parent_path)
        if parent is None:
            self._emit_walk(
                f"miss inst={inst_leaf} under {parent_path} ({reason})  "
                f"(no parent elaboration row)"
            )
            return
        self._emit_walk(
            format_path_walk_miss_line(
                parent_path,
                parent,
                inst_leaf,
                reason=reason,
            )
        )
        spine_end = parent_path
        spine_title = (
            f"walked (target {target_path} stopped)" if target_path else "walked"
        )
        if self._trace_streams():
            self._emit_walk_spine(spine_end, title=spine_title)
        elif target_path:
            self._emit_walk(
                f"walked spine -> {spine_end} (target {target_path} stopped)"
            )

    def flush_pending_misses(self) -> None:
        """Emit miss lines only for walk targets that never resolved."""
        pending = list(self._pending_misses)
        self._pending_misses.clear()
        for miss in pending:
            if miss.target_path in self.rows_by_path:
                continue
            resolved = _walk_target_from_spec(miss.target_path, self)
            if resolved and resolved in self.rows_by_path:
                continue
            self._emit_walk_miss(
                miss.parent_path,
                miss.inst_leaf,
                reason=miss.reason,
                target_path=miss.target_path,
            )

    def _sync_db_stats(self) -> None:
        self.stats.files_regex_scanned = self.mod_db.files_regex_scanned
        self.stats.files_validated = self.mod_db.files_validated
        self.stats.cache_regex_hits = self.mod_db.cache_regex_hits
        self.stats.cache_validated_hits = self.mod_db.cache_validated_hits
        self.stats.files_scanned = (
            self.mod_db.files_regex_scanned + self.mod_db.files_validated
        )

    def rows(self) -> List[FlatRow]:
        return list(self.rows_by_path.values())

    def _add_row(
        self,
        mod: str,
        path: str,
        depth: int,
        parent: Optional[str],
        *,
        inst_leaf: str,
        file_path: str,
        stop_reason: str,
        param_ctx: Mapping[str, str],
    ) -> None:
        if path in self.rows_by_path:
            return
        self.rows_by_path[path] = FlatRow(
            full_path=path,
            inst_leaf=inst_leaf,
            module=mod,
            depth=depth,
            parent_path=parent,
            file=file_path,
            stop_reason=stop_reason,
            via_filelist=self.index.filelist_for(file_path),
            filelist_chain=self.index.filelist_chain_for(file_path),
            param_ctx=dict(param_ctx),
        )
        self._emit_walk_node(path)

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
            inst_leaf=self.top,
            file_path=rec.file_path,
            stop_reason=stop,
            param_ctx=resolve_param_map(rec.raw_params),
        )

    def _load_module(
        self,
        module_name: str,
        *,
        expect_inst: Optional[Tuple[str, str]] = None,
        parent_ctx: Optional[Mapping[str, str]] = None,
        scope_anchor: str = "",
    ) -> bool:
        had = self.index.get_module(module_name)
        if not self.mod_db.ensure_module_in_index(
            module_name,
            expect_inst=expect_inst,
            parent_ctx=parent_ctx,
            scope_anchor=scope_anchor,
        ):
            self._sync_db_stats()
            self._emit_walk(
                f"pw-db load failed module={module_name!r} "
                f"{self.mod_db.format_status_line()}"
            )
            return False
        rec = self.index.get_module(module_name)
        if rec is None:
            self._sync_db_stats()
            return False
        if had is None or (had.file_path or "") != (rec.file_path or ""):
            self.stats.modules_loaded += 1
        self._sync_db_stats()
        return True

    def _child_edge(self, parent_path: str, inst_leaf: str) -> Optional[InstanceEdge]:
        row = self.rows_by_path.get(parent_path)
        if row is None:
            return None
        edge = self.mod_db.resolve_child_edge(
            row.module,
            row.param_ctx,
            inst_leaf,
            current_file=row.file,
        )
        self._sync_db_stats()
        return edge

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
        if not self._load_module(edge.child_module, scope_anchor=parent.file):
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
            inst_leaf=inst_leaf,
            file_path=rec.file_path,
            stop_reason=stop,
            param_ctx=pmap,
        )
        return child_path

    @staticmethod
    def _inst_leaf_prefix(remainder: str) -> str:
        """First hierarchy segment of *remainder* (handles ``c[0][1].d``)."""
        seg, _ = _read_hier_inst_path(remainder, 0)
        if seg:
            return seg
        return remainder.split(".", 1)[0]

    @staticmethod
    def _remainder_matches_inst(remainder: str, inst_name: str) -> bool:
        if remainder == inst_name:
            return True
        prefix = inst_name + "."
        return (
            remainder.startswith(prefix)
            or remainder.lower().startswith(prefix.lower())
        )

    def _resolve_child_step(
        self,
        parent_path: str,
        remainder: str,
    ) -> Tuple[str, Optional[InstanceEdge]]:
        """Match longest folded instance name at start of *remainder*."""
        row = self.rows_by_path.get(parent_path)
        if row is None or not remainder:
            return "", None
        rec = self.index.get_module(row.module)
        if rec is None:
            return "", None
        pmap = resolve_param_map(rec.raw_params, parent=row.param_ctx)
        edges = self.index.instances_for(row.module, row.param_ctx, {})
        best_name = ""
        best_edge: Optional[InstanceEdge] = None
        for edge in edges:
            for name in expand_inst_names(edge.inst_name, "", pmap):
                if self._remainder_matches_inst(remainder, name):
                    if len(name) > len(best_name):
                        best_name = name
                        best_edge = edge
        if best_edge is not None:
            return best_name, best_edge
        seg = self._inst_leaf_prefix(remainder)
        if not seg:
            return "", None
        edge = self._child_edge(parent_path, seg)
        if edge is not None:
            return seg, edge
        return "", None

    def ensure_path(self, instance_path: str) -> bool:
        """Walk ``top.u_child...`` loading RTL files on demand."""
        path = instance_path.strip()
        if not path:
            return False
        if path != self.top and not path.startswith(self.top + "."):
            return False
        self.mod_db._set_phase("searching", detail=path)
        if path in self.rows_by_path:
            self._clear_pending_misses(path)
            return True
        self.ensure_root()
        if path == self.top:
            self._clear_pending_misses(path)
            return True
        cur = self.top
        remainder = path[len(self.top) + 1 :] if len(path) > len(self.top) else ""
        while remainder:
            nxt = f"{cur}.{remainder}"
            if nxt in self.rows_by_path:
                cur = nxt
                remainder = ""
                break
            inst_name, edge = self._resolve_child_step(cur, remainder)
            if edge is None or not inst_name:
                row = self.rows_by_path.get(cur)
                parent_mod = row.module if row else "?"
                miss_leaf = self._inst_leaf_prefix(remainder)
                snap = self.mod_db.module_to_files_snapshot().get(parent_mod, [])
                cand = "; ".join(Path(f).name for f in snap[:8])
                have = ""
                type_hint = ""
                parent_rec = self.index.get_module(parent_mod) if parent_mod else None
                if parent_rec is not None:
                    edges = self.index.instances_for(
                        parent_mod,
                        row.param_ctx if row else {},
                        {},
                    )
                    if edges:
                        have = "; ".join(
                            f"{e.inst_name}->{e.child_module}" for e in edges[:8]
                        )
                    miss_lower = miss_leaf.lower()
                    for inst_edge in edges:
                        if inst_edge.child_module.lower() == miss_lower:
                            type_hint = (
                                f"; hint: {miss_leaf!r} is module type — "
                                f"use inst name {inst_edge.inst_name!r} "
                                f"(path-walk uses instance names, not module types)"
                            )
                            break
                    if not type_hint:
                        indexed = sorted(
                            {
                                e.inst_name
                                for e in edges
                                if e.inst_name.startswith(miss_leaf + "[")
                                or (
                                    e.inst_name.lower().startswith(
                                        miss_lower + "["
                                    )
                                )
                            }
                        )
                        if indexed:
                            type_hint = (
                                f"; hint: {miss_leaf!r} is an array instance — "
                                f"use indexed name e.g. {indexed[0]!r}"
                            )
                self._queue_walk_miss(
                    cur,
                    miss_leaf,
                    reason=(
                        "instance edge not found in parent module"
                        + (f"; have: {have}" if have else "")
                        + type_hint
                        + (
                            f"; pw-db {parent_mod} files: {cand or '(tier0 none)'}"
                            if parent_mod
                            else ""
                        )
                    ),
                    target_path=path,
                )
                self.mod_db.write_module_index_snapshot()
                return False
            attached = self._attach_child(cur, inst_name, edge)
            if attached is None:
                child_mod = edge.child_module or "?"
                self._queue_walk_miss(
                    cur,
                    inst_name,
                    reason=f"child module {child_mod!r} not loaded",
                    target_path=path,
                )
                return False
            cur = attached
            remainder = remainder[len(inst_name) :].lstrip(".")
        self.stats.paths_walked += 1
        ok = path in self.rows_by_path
        if ok:
            self._clear_pending_misses(path)
        return ok

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


def _walk_target_from_spec(spec: str, state: PathWalkState) -> str:
    """
    Hierarchy path to walk for a connect/endpoint spec.

    Uses the full instance-name chain from *spec*. Does not truncate to the
    first missing prefix (that truncation is only for error reporting).
    """
    from scan_inst.connect_endpoints import _port_exists

    text = spec.strip()
    if not text:
        return ""
    lookup = state.rows_by_path
    if text in lookup:
        return text
    parts = text.split(".")
    for i in range(len(parts) - 1, 0, -1):
        hier = ".".join(parts[:i])
        row = lookup.get(hier)
        if row is None:
            continue
        port = ".".join(parts[i:])
        if _port_exists(state.index, row, port, top=state.top):
            return hier
    return text


def _inst_path_from_spec(
    spec: str,
    state: PathWalkState,
) -> str:
    """Resolved hierarchy prefix for error messages (may stop at first miss)."""
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


def _path_walk_trace_emit(
    message: str,
    *,
    trace_stream: Optional[TextIO] = None,
    trace_log_fh: Optional[TextIO] = None,
    on_progress: Optional[Callable[[str], None]] = None,
) -> None:
    if not message or not path_walk_trace_show_message(message):
        return
    streams: List[TextIO] = []
    if trace_stream is not None:
        streams.append(trace_stream)
    if trace_log_fh is not None:
        streams.append(trace_log_fh)
    if streams:
        for stream in streams:
            emit_path_walk_log(message, stream=stream)
    elif on_progress is not None:
        on_progress(f"path-walk: {message}")


def _wire_db_trace_to_state(mod_db: PathWalkModuleDb, state: PathWalkState) -> None:
    mod_db._on_trace = state._emit_walk


def build_path_walk_state_from_specs(
    index: DesignIndex,
    top: str,
    specs: Sequence[str],
    mod_db: PathWalkModuleDb,
    *,
    expand_subtrees: Sequence[str] = (),
    on_progress: Optional[Callable[[str], None]] = None,
    trace_stream: Optional[TextIO] = None,
    trace_log_path: Optional[Path] = None,
    trace_log_fh: Optional[TextIO] = None,
    close_trace_log: bool = True,
) -> PathWalkState:
    """Walk endpoint specs; optionally expand instance subtrees for cone / inst-trace."""
    opened_log = False
    if trace_log_fh is None and trace_log_path is not None:
        trace_log_fh = open_path_walk_trace_log(trace_log_path)
        opened_log = True
    try:
        state = PathWalkState(
            index=index,
            top=top,
            mod_db=mod_db,
            on_progress=on_progress,
            trace_stream=trace_stream,
            _trace_log=trace_log_fh,
        )
        _wire_db_trace_to_state(mod_db, state)
        state.ensure_root()
        spec_list = [str(s).strip() for s in specs if str(s).strip()]
        if on_progress:
            on_progress(f"path-walk: {len(spec_list)} endpoint spec(s)")
        for prefix in _sorted_prefixes(spec_list):
            state.ensure_path(prefix)
        for spec in spec_list:
            inst = _walk_target_from_spec(spec, state)
            if inst:
                state.ensure_path(inst)
        for subtree_root in expand_subtrees:
            root = str(subtree_root).strip()
            if not root:
                continue
            if state.ensure_path(root):
                state._expand_subtree(root)
                state.stats.subtrees_expanded += 1
        state.flush_pending_misses()
        return state
    finally:
        if opened_log and close_trace_log and trace_log_fh is not None:
            trace_log_fh.close()


def build_path_walk_state(
    index: DesignIndex,
    top: str,
    request: ConnectivityRequest,
    mod_db: PathWalkModuleDb,
    *,
    on_progress: Optional[Callable[[str], None]] = None,
    trace_stream: Optional[TextIO] = None,
    trace_log_path: Optional[Path] = None,
    trace_log_fh: Optional[TextIO] = None,
    close_trace_log: bool = True,
) -> PathWalkState:
    opened_log = False
    if trace_log_fh is None and trace_log_path is not None:
        trace_log_fh = open_path_walk_trace_log(trace_log_path)
        opened_log = True
    try:
        state = PathWalkState(
            index=index,
            top=top,
            mod_db=mod_db,
            on_progress=on_progress,
            trace_stream=trace_stream,
            _trace_log=trace_log_fh,
        )
        _wire_db_trace_to_state(mod_db, state)
        state.ensure_root()
        specs = endpoint_specs_from_request(request)
        if on_progress:
            on_progress(f"path-walk: {len(specs)} endpoint spec(s)")
        for prefix in _sorted_prefixes(specs):
            state.ensure_path(prefix)
        seen_lca: Set[Tuple[str, str]] = set()
        for chk in request.checks:
            a = _walk_target_from_spec(chk.endpoint_a, state)
            b = _walk_target_from_spec(chk.endpoint_b, state)
            key = (a, b)
            if key in seen_lca:
                continue
            seen_lca.add(key)
            state.ensure_lca_subtree(a, b)
        state.flush_pending_misses()
        return state
    finally:
        if opened_log and close_trace_log and trace_log_fh is not None:
            trace_log_fh.close()


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
    cache_dir: Optional[Path] = None,
    no_cache: bool = False,
    on_progress: Optional[Callable[[str], None]] = None,
    trace_stream: Optional[TextIO] = None,
    trace_log_path: Optional[Path] = None,
) -> Tuple[DesignIndex, PathWalkState, str]:
    """On-demand index + hierarchy rows for arbitrary endpoint specs."""
    defines = dict(fl.defines)
    defines.update(extra_defines or {})
    trace_log_fh: Optional[TextIO] = None
    opened_log = False
    if trace_log_path is not None:
        trace_log_fh = open_path_walk_trace_log(trace_log_path)
        opened_log = True
    try:
        index, mod_db = create_path_walk_index(
            fl,
            top,
            defines=defines,
            ignore_paths=ignore_paths,
            ignore_path_files=ignore_path_files,
            ignore_modules=ignore_modules,
            ignore_filelists=ignore_filelists,
            cache_dir=cache_dir,
            no_cache=no_cache,
            on_progress=on_progress,
            trace_stream=trace_stream,
            trace_log_fh=trace_log_fh,
        )
        tops = resolve_top_modules(index, top=top, filelist_tops=fl.top_modules)
        top_name = tops[0]
        state = build_path_walk_state_from_specs(
            index,
            top_name,
            specs,
            mod_db,
            on_progress=on_progress,
            trace_stream=trace_stream,
            trace_log_fh=trace_log_fh,
            close_trace_log=False,
        )
        extra_roots = list(expand_subtrees)
        for spec in specs:
            inst = _walk_target_from_spec(spec, state)
            if inst and inst not in extra_roots:
                extra_roots.append(inst)
        for subtree_root in extra_roots:
            root = str(subtree_root).strip()
            if not root:
                continue
            if state.ensure_path(root):
                state._expand_subtree(root)
                state.stats.subtrees_expanded += 1
        state._sync_db_stats()
        if on_progress:
            on_progress(
                f"path-walk: {len(state.rows_by_path)} instance row(s), "
                f"{state.stats.modules_loaded} module(s) loaded, "
                f"tier0={state.stats.files_regex_scanned} tier1={state.stats.files_validated} "
                f"cache={state.stats.cache_regex_hits}+{state.stats.cache_validated_hits}"
            )
        return index, state, top_name
    finally:
        if opened_log and trace_log_fh is not None:
            trace_log_fh.close()


def create_path_walk_index(
    fl: FilelistResult,
    top: str,
    *,
    defines: Mapping[str, str],
    ignore_paths: Sequence[str] = (),
    ignore_path_files: Sequence[str] = (),
    ignore_modules: Sequence[str] = (),
    ignore_filelists: Sequence[str] = (),
    cache_dir: Optional[Path] = None,
    no_cache: bool = False,
    on_progress: Optional[Callable[[str], None]] = None,
    trace_stream: Optional[TextIO] = None,
    trace_log_fh: Optional[TextIO] = None,
) -> Tuple[DesignIndex, PathWalkModuleDb]:
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
    sources = [str(p) for p in fl.source_files]
    cache_key = path_walk_db_cache_key(
        sources,
        defines=defines,
        include_dirs=[str(p) for p in fl.include_dirs],
        skip_path_patterns=path_patterns,
    )
    def _db_trace(msg: str) -> None:
        _path_walk_trace_emit(
            msg,
            trace_stream=trace_stream,
            trace_log_fh=trace_log_fh,
            on_progress=on_progress,
        )

    from scan_inst.filelist import filelist_provenance_maps

    via_map, _chain_map = filelist_provenance_maps(fl)
    mod_db = PathWalkModuleDb(
        sources,
        index,
        include_dirs=[str(p) for p in fl.include_dirs],
        defines=dict(defines),
        skip_path_patterns=path_patterns,
        cache_dir=cache_dir,
        cache_key=cache_key,
        no_cache=no_cache,
        on_trace=_db_trace,
        on_progress=on_progress,
        file_via_filelist=via_map,
        filelist_children={
            str(k): list(v) for k, v in (fl.filelist_children or {}).items()
        },
    )
    from scan_inst.progress import ProgressHeartbeat

    with ProgressHeartbeat(
        on_progress or (lambda _msg: None),
        "path-walk",
        enabled=on_progress is not None,
        get_detail=mod_db.heartbeat_detail,
    ):
        mod_db.remember_index_modules()
        if on_progress:
            on_progress(mod_db.format_status_line())
        mod_db._set_phase("mapping", detail=f"top {top}")
        top_file = mod_db.find_module_decl_file(top)
        if not top_file:
            raise ValueError(f"top module {top!r} not found in filelist sources")
        if on_progress:
            on_progress(f"path-walk: seed top {top} ({Path(top_file).name})")
        if not mod_db.ensure_module_in_index(top, scope_anchor=top_file):
            raise ValueError(f"top module {top!r} could not be loaded from {top_file}")
    return index, mod_db


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
    cache_dir: Optional[Path] = None,
    no_cache: bool = False,
    on_progress: Optional[Callable[[str], None]] = None,
    trace_stream: Optional[TextIO] = None,
    trace_log_path: Optional[Path] = None,
) -> Tuple[ConnectivityBatchResult, DesignIndex, PathWalkState]:
    """
    Path-walk batch connectivity: on-demand RTL + shared :class:`ConnectivitySession`.

    Uses ``jobs=1`` internally so ``mod_cache`` is shared across all checks.
    """
    defines = dict(fl.defines)
    defines.update(extra_defines or {})
    defines.update(request.defines)

    trace_log_fh: Optional[TextIO] = None
    opened_log = False
    if trace_log_path is not None:
        trace_log_fh = open_path_walk_trace_log(trace_log_path)
        opened_log = True
    try:
        index, mod_db = create_path_walk_index(
            fl,
            top,
            defines=defines,
            ignore_paths=ignore_paths,
            ignore_path_files=ignore_path_files,
            ignore_modules=ignore_modules,
            ignore_filelists=ignore_filelists,
            cache_dir=cache_dir,
            no_cache=no_cache,
            on_progress=on_progress,
            trace_stream=trace_stream,
            trace_log_fh=trace_log_fh,
        )
        tops = resolve_top_modules(index, top=top, filelist_tops=fl.top_modules)
        top_name = tops[0]

        state = build_path_walk_state(
            index,
            top_name,
            request,
            mod_db,
            on_progress=on_progress,
            trace_stream=trace_stream,
            trace_log_fh=trace_log_fh,
            close_trace_log=False,
        )
        state._sync_db_stats()
        if on_progress:
            on_progress(
                f"path-walk: {len(state.rows_by_path)} instance row(s), "
                f"{state.stats.modules_loaded} module(s) loaded, "
                f"tier0={state.stats.files_regex_scanned} tier1={state.stats.files_validated} "
                f"cache={state.stats.cache_regex_hits}+{state.stats.cache_validated_hits}"
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
    finally:
        if opened_log and trace_log_fh is not None:
            trace_log_fh.close()