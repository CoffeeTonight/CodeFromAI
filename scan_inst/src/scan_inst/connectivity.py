"""Structural COI connectivity (public API and batch session)."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any, Dict, IO, List, Mapping, Optional, Sequence, Tuple, Union

from scan_inst.connect_endpoints import (
    _module_index,
    _port_param_ctx,
    _prune_rows_lca,
    parse_connect_endpoint,
    resolve_endpoint,
)
from scan_inst.connect_request import (
    ConnectivityRequest,
    load_connect_request,
    parse_connect_request_json,
)
from scan_inst.connect_scan import (
    ModuleConnectIndex,
    build_module_connect_index,
    collect_design_defines,
)
from scan_inst.connect_search import (
    _bidirectional_coi,
    _connect_note,
    _forward_coi_to_scope,
    _resolve_over_approximate_if,
)
from scan_inst.index import DesignIndex
from scan_inst.models import ConnectEndpoint, ConnectHop, ConnectResult, ElabIndex, FlatRow

__all__ = [
    "ConnectivityBatchResult",
    "ConnectivitySession",
    "build_module_connect_index",
    "check_connectivity",
    "check_connectivity_batch",
    "emit_connect_trace_log",
    "format_connect_hop",
    "format_connect_result_row",
    "format_connect_results_tsv",
    "format_connect_trace_report",
    "load_connect_pairs",
    "parse_connect_endpoint",
    "parse_connect_pairs_json",
    "print_connect_trace_reports",
    "resolve_endpoint",
    "run_connectivity_request",
]

def format_connect_hop(hop: ConnectHop) -> str:
    return f"[{hop.kind}] {hop.detail}"


def format_connect_trace_report(result: ConnectResult) -> str:
    """Multi-line evidence report for a connectivity result."""
    lines = [
        f"check: {result.endpoint_a.spec} -> {result.endpoint_b.spec}",
        f"connected: {result.connected}  mode: {result.mode}  note: {result.note}",
    ]
    if result.errors:
        lines.append("errors:")
        lines.extend(f"  - {e}" for e in result.errors)
    if result.connected and result.hops:
        lines.append("path evidence:")
        for i, hop in enumerate(result.hops, 1):
            lines.append(f"  {i}. {format_connect_hop(hop)}")
    elif result.connected:
        lines.append("path evidence: (no hop detail; enable connect_trace / connect_log)")
    return "\n".join(lines) + "\n"


def emit_connect_trace_log(
    result: ConnectResult,
    *,
    stream: IO[str] = sys.stderr,
    check_prefix: str = "",
) -> None:
    """Emit numbered path-evidence steps for a connected (or traced) result."""
    prefix = "[scan-inst connect]"
    if check_prefix:
        prefix = f"{prefix} [{check_prefix}]"
    header = f"{prefix} {result.endpoint_a.spec} -> {result.endpoint_b.spec}"
    print(header, file=stream, flush=True)
    if result.errors:
        for err in result.errors:
            print(f"{prefix}   error: {err}", file=stream, flush=True)
    if not result.connected:
        print(f"{prefix}   not connected ({result.note})", file=stream, flush=True)
        return
    if not result.hops:
        print(f"{prefix}   connected ({result.note}); no hop detail", file=stream, flush=True)
        return
    for i, hop in enumerate(result.hops, 1):
        print(f"{prefix}   {i}. {format_connect_hop(hop)}", file=stream, flush=True)


def print_connect_trace_reports(
    results: Sequence[ConnectResult],
    *,
    stream: IO[str],
    title: str = "connectivity path evidence",
) -> None:
    """Print human-readable path-evidence blocks for terminal or log file."""
    if not results:
        return
    print(f"\n--- {title} ---", file=stream, flush=True)
    for result in results:
        if result.check_id:
            print(f"# check_id: {result.check_id}", file=stream, flush=True)
        print(format_connect_trace_report(result), end="", file=stream, flush=True)


def _effective_defines(
    index: DesignIndex,
    defines: Mapping[str, str] | None,
) -> Dict[str, str]:
    return {**collect_design_defines(index), **dict(defines or {})}


def _connect_pair(
    endpoint_a: str,
    endpoint_b: str,
    *,
    rows: Sequence[FlatRow],
    index: DesignIndex,
    top: str,
    effective_defines: Mapping[str, str],
    trace: bool = False,
    strict_generate: bool = False,
    ff_barrier: bool = True,
    over_approximate_if: Optional[bool] = None,
    mod_cache: Dict[Tuple[str, str], ModuleConnectIndex],
    param_ctx_cache: Dict[str, Mapping[str, str]],
    check_id: str = "",
    elab_index: Optional[ElabIndex] = None,
    rows_by_path: Optional[Mapping[str, FlatRow]] = None,
) -> ConnectResult:
    lookup = (
        rows_by_path
        if rows_by_path is not None
        else (elab_index.rows_by_path if elab_index is not None else None)
    )
    ep_a, err_a = resolve_endpoint(
        endpoint_a,
        rows,
        index,
        top=top,
        require_port=False,
        rows_by_path=lookup,
    )
    ep_b, err_b = resolve_endpoint(
        endpoint_b,
        rows,
        index,
        top=top,
        require_port=False,
        rows_by_path=lookup,
    )
    errors = list(err_a) + list(err_b)

    if errors:
        mode = _mode(ep_a, ep_b) if ep_a.module and ep_b.module else "unknown"
        return ConnectResult(
            ep_a,
            ep_b,
            False,
            mode,
            errors=errors,
            check_id=check_id,
        )

    if _has_port(ep_a) and not ep_a.port_found:
        return ConnectResult(
            ep_a, ep_b, False, _mode(ep_a, ep_b), errors=errors, check_id=check_id
        )
    if _has_port(ep_b) and not ep_b.port_found:
        return ConnectResult(
            ep_a, ep_b, False, _mode(ep_a, ep_b), errors=errors, check_id=check_id
        )

    pruned = _prune_rows_lca(rows, ep_a.inst_path, ep_b.inst_path)
    mode = _mode(ep_a, ep_b)

    if mode == "port-port":
        start = (ep_a.inst_path, ep_a.port_name or "")
        goal = (ep_b.inst_path, ep_b.port_name or "")
        ok, hops, mod_n = _bidirectional_coi(
            start,
            goal,
            rows=pruned,
            index=index,
            top=top,
            defines=effective_defines,
            trace=trace,
            strict_generate=strict_generate,
            ff_barrier=ff_barrier,
            over_approximate_if=over_approximate_if,
            mod_cache=mod_cache,
            param_ctx_cache=param_ctx_cache,
            elab_index=elab_index,
        )
        return ConnectResult(
            ep_a,
            ep_b,
            ok,
            mode,
            hops=hops,
            errors=errors,
            note=_connect_note(ok, mod_n),
            check_id=check_id,
        )

    if mode == "port-hierarchy":
        port_ep = ep_a if _has_port(ep_a) else ep_b
        hier_ep = ep_b if _has_port(ep_a) else ep_a
        start = (port_ep.inst_path, port_ep.port_name or "")
        ok, hops, mod_n = _forward_coi_to_scope(
            start,
            hier_ep.inst_path,
            rows=pruned,
            index=index,
            top=top,
            defines=effective_defines,
            trace=trace,
            strict_generate=strict_generate,
            ff_barrier=ff_barrier,
            over_approximate_if=over_approximate_if,
            mod_cache=mod_cache,
            param_ctx_cache=param_ctx_cache,
            elab_index=elab_index,
        )
        return ConnectResult(
            ep_a,
            ep_b,
            ok,
            mode,
            hops=hops,
            errors=errors,
            note=_connect_note(ok, mod_n, hier=True),
            check_id=check_id,
        )

    return ConnectResult(
        ep_a,
        ep_b,
        ep_a.inst_path == ep_b.inst_path
        or _is_ancestor(ep_a.inst_path, ep_b.inst_path)
        or _is_ancestor(ep_b.inst_path, ep_a.inst_path),
        "hierarchy-hierarchy",
        errors=errors,
        note="same or ancestor/descendant (no port trace)",
        check_id=check_id,
    )


@dataclass
class ConnectivitySession:
    """
    Reusable connectivity checker for many endpoint pairs.

    ``mod_cache`` and ``param_ctx_cache`` persist across ``check`` / ``check_many``
    so repeated queries through the same RTL modules (e.g. array fan-out) avoid
    rebuilding ``ModuleConnectIndex`` graphs.
    """

    rows: Sequence[FlatRow]
    index: DesignIndex
    top: str = ""
    defines: Mapping[str, str] = field(default_factory=dict)
    strict_generate: bool = False
    ff_barrier: bool = True
    over_approximate_if: Optional[bool] = None
    mod_cache: Dict[Tuple[str, str], ModuleConnectIndex] = field(default_factory=dict)
    param_ctx_cache: Dict[str, Mapping[str, str]] = field(default_factory=dict)
    elab_index: Optional[ElabIndex] = None

    def __post_init__(self) -> None:
        if self.elab_index is None and self.rows:
            self.elab_index = ElabIndex.from_rows(self.rows)
        if not self.top and self.rows:
            self.top = self.rows[0].full_path.split(".", 1)[0]
        self._effective_defines = _effective_defines(self.index, self.defines)

    @property
    def rows_by_path(self) -> Dict[str, FlatRow]:
        if self.elab_index is not None:
            return self.elab_index.rows_by_path
        return {r.full_path: r for r in self.rows}

    @property
    def modules_cached(self) -> int:
        return len(self.mod_cache)

    def clear_cache(self) -> None:
        self.mod_cache.clear()
        self.param_ctx_cache.clear()

    def check(
        self,
        endpoint_a: str,
        endpoint_b: str,
        *,
        trace: bool = False,
        check_id: str = "",
    ) -> ConnectResult:
        return _connect_pair(
            endpoint_a,
            endpoint_b,
            rows=self.rows,
            index=self.index,
            top=self.top,
            effective_defines=self._effective_defines,
            trace=trace,
            strict_generate=self.strict_generate,
            ff_barrier=self.ff_barrier,
            over_approximate_if=self.over_approximate_if,
            mod_cache=self.mod_cache,
            param_ctx_cache=self.param_ctx_cache,
            check_id=check_id,
            elab_index=self.elab_index,
            rows_by_path=self.rows_by_path,
        )

    def check_many(
        self,
        pairs: Sequence[Tuple[str, str]],
        *,
        trace: bool = False,
    ) -> List[ConnectResult]:
        return [self.check(a, b, trace=trace) for a, b in pairs]

    def run_request(
        self,
        request: ConnectivityRequest,
        *,
        trace: Optional[bool] = None,
    ) -> ConnectivityBatchResult:
        use_trace = request.trace if trace is None else trace
        results = tuple(
            self.check(
                chk.endpoint_a,
                chk.endpoint_b,
                trace=use_trace,
                check_id=chk.check_id,
            )
            for chk in request.checks
        )
        return ConnectivityBatchResult(
            results=results,
            modules_cached=self.modules_cached,
        )

    def prewarm_inst(self, inst_path: str) -> bool:
        """Build ``ModuleConnectIndex`` for the module at *inst_path* (if known)."""
        row = self.rows_by_path.get(inst_path)
        if row is None:
            return False
        over_approx = _resolve_over_approximate_if(
            self.strict_generate,
            self.over_approximate_if,
        )
        pmap = _port_param_ctx(self.index, row, self.top)
        self.param_ctx_cache[row.full_path] = pmap
        _module_index(
            self.mod_cache,
            self.index,
            row.module,
            pmap,
            defines=self._effective_defines,
            over_approximate_if=over_approx,
            ff_barrier=self.ff_barrier,
        )
        return True


def check_connectivity(
    endpoint_a: str,
    endpoint_b: str,
    *,
    rows: Sequence[FlatRow],
    index: DesignIndex,
    top: str = "",
    defines: Mapping[str, str] | None = None,
    trace: bool = False,
    strict_generate: bool = False,
    ff_barrier: bool = True,
    over_approximate_if: Optional[bool] = None,
) -> ConnectResult:
    if not top and rows:
        top = rows[0].full_path.split(".", 1)[0]
    return _connect_pair(
        endpoint_a,
        endpoint_b,
        rows=rows,
        index=index,
        top=top,
        effective_defines=_effective_defines(index, defines),
        trace=trace,
        strict_generate=strict_generate,
        ff_barrier=ff_barrier,
        over_approximate_if=over_approximate_if,
        mod_cache={},
        param_ctx_cache={},
    )


@dataclass(frozen=True)
class ConnectivityBatchResult:
    """Outcome of ``check_connectivity_batch`` (shared module-index cache)."""

    results: Tuple[ConnectResult, ...]
    modules_cached: int


def _session_from_options(
    *,
    rows: Sequence[FlatRow],
    index: DesignIndex,
    top: str,
    defines: Mapping[str, str] | None,
    trace: bool,
    strict_generate: bool,
    ff_barrier: bool,
    over_approximate_if: Optional[bool],
) -> ConnectivitySession:
    return ConnectivitySession(
        rows=rows,
        index=index,
        top=top,
        defines=dict(defines or {}),
        strict_generate=strict_generate,
        ff_barrier=ff_barrier,
        over_approximate_if=over_approximate_if,
    )


def check_connectivity_batch(
    pairs: Sequence[Tuple[str, str]],
    *,
    rows: Sequence[FlatRow],
    index: DesignIndex,
    top: str = "",
    defines: Mapping[str, str] | None = None,
    trace: bool = False,
    strict_generate: bool = False,
    ff_barrier: bool = True,
    over_approximate_if: Optional[bool] = None,
) -> ConnectivityBatchResult:
    """
    Batch connectivity with the same options as ``check_connectivity``.

    Reuses ``ModuleConnectIndex`` across *pairs* (array fan-out, bus checks, …).
    """
    session = _session_from_options(
        rows=rows,
        index=index,
        top=top,
        defines=defines,
        trace=trace,
        strict_generate=strict_generate,
        ff_barrier=ff_barrier,
        over_approximate_if=over_approximate_if,
    )
    results = tuple(session.check(a, b, trace=trace) for a, b in pairs)
    return ConnectivityBatchResult(
        results=results,
        modules_cached=session.modules_cached,
    )


def run_connectivity_request(
    request: ConnectivityRequest,
    *,
    rows: Sequence[FlatRow],
    index: DesignIndex,
    top: str = "",
    extra_defines: Mapping[str, str] | None = None,
) -> ConnectivityBatchResult:
    """Run a full JSON connectivity request (checks + options)."""
    top_name = request.top or top
    if not top_name and rows:
        top_name = rows[0].full_path.split(".", 1)[0]
    merged_defines = _effective_defines(index, extra_defines)
    merged_defines.update(request.defines)
    session = ConnectivitySession(
        rows=rows,
        index=index,
        top=top_name,
        defines=merged_defines,
        strict_generate=request.strict_generate,
        ff_barrier=not request.include_ff,
        over_approximate_if=request.over_approximate_if,
    )
    return session.run_request(request)


def format_connect_result_row(result: ConnectResult) -> str:
    err_text = " | ".join(result.errors)
    hop_text = " | ".join(format_connect_hop(h) for h in result.hops)
    return (
        f"{result.check_id}\t{result.endpoint_a.spec}\t{result.endpoint_b.spec}\t"
        f"{result.connected}\t{result.mode}\t{result.note}\t"
        f"{err_text}\t"
        f"{hop_text}"
    )


def format_connect_results_tsv(
    results: Sequence[ConnectResult],
    *,
    modules_cached: Optional[int] = None,
) -> str:
    lines = [
        "check_id\tendpoint_a\tendpoint_b\tconnected\tmode\tnote\terrors\thops",
        *(format_connect_result_row(r) for r in results),
    ]
    if modules_cached is not None:
        lines.append(f"# modules_cached\t{modules_cached}")
    return "\n".join(lines) + "\n"


def parse_connect_pairs_json(data: Any) -> List[Tuple[str, str]]:
    """Backward-compatible pairs-only JSON parse."""
    req = parse_connect_request_json(data)
    return [(c.endpoint_a, c.endpoint_b) for c in req.checks]


def load_connect_pairs(path: Union[str, Path]) -> List[Tuple[str, str]]:
    """Backward-compatible pairs loader (text or minimal JSON)."""
    return [(c.endpoint_a, c.endpoint_b) for c in load_connect_request(path).checks]


def _has_port(ep: ConnectEndpoint) -> bool:
    return bool(ep.port_name)


def _mode(a: ConnectEndpoint, b: ConnectEndpoint) -> str:
    if _has_port(a) and _has_port(b):
        return "port-port"
    if _has_port(a) or _has_port(b):
        return "port-hierarchy"
    return "hierarchy-hierarchy"


def _is_ancestor(ancestor: str, path: str) -> bool:
    return path.startswith(ancestor + ".")