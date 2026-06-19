"""Waypoint-qualified fanout trace for connectivity checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple

from scan_inst.cone import (
    _ConeCtx,
    _boundary_at_state,
    _cached_cone_mod,
    _expand_fanout,
    _state_key,
)
from scan_inst.connect_endpoints import resolve_endpoint
from scan_inst.connect_scan import lookup_edge_prov, net_representative
from scan_inst.index import DesignIndex
from scan_inst.inst_trace import _ports_for_instance
from scan_inst.models import ConnectEndpoint, ConnectResult, FlatRow
NetState = Tuple[str, str]
BfsState = Tuple[str, str, bool]


@dataclass(frozen=True)
class WaypointFanoutEvent:
    source: str
    event_kind: str
    scope: str
    net: str
    rtl_file: str
    rtl_line: int
    waypoint_hit: str
    waypoint_qualified: str
    is_terminator: str


@dataclass
class WaypointSet:
    port_nets: Set[Tuple[str, str]] = field(default_factory=set)
    inst_prefixes: Set[str] = field(default_factory=set)


def _yn(flag: bool) -> str:
    return "Y" if flag else "N"


def _is_inst_spec(spec: str, ep: ConnectEndpoint, rows_by_path: Mapping[str, FlatRow]) -> bool:
    text = spec.strip()
    if text in rows_by_path:
        return True
    return text == ep.inst_path and not ep.port_name


def normalize_waypoints(
    specs: Sequence[str],
    rows: Sequence[FlatRow],
    index: DesignIndex,
    top: str,
) -> Tuple[WaypointSet, List[str]]:
    rows_by_path = {r.full_path: r for r in rows}
    waypoints = WaypointSet()
    errors: List[str] = []
    for spec in specs:
        text = str(spec).strip()
        if not text:
            errors.append("waypoint spec must be non-empty")
            continue
        ep, ep_errs = resolve_endpoint(
            text,
            rows,
            index,
            top=top,
            require_port=False,
            rows_by_path=rows_by_path,
        )
        errors.extend(ep_errs)
        if ep_errs:
            continue
        if _is_inst_spec(text, ep, rows_by_path):
            waypoints.inst_prefixes.add(ep.inst_path)
            continue
        if ep.port_name:
            waypoints.port_nets.add((ep.inst_path, ep.port_name))
        else:
            errors.append(f"waypoint not resolved: {text}")
    return waypoints, errors


def expand_fanout_origins(
    specs: Sequence[str],
    *,
    rows: Sequence[FlatRow],
    index: DesignIndex,
    top: str,
) -> Tuple[List[Tuple[str, str, str]], List[str]]:
    """Return (source_label, scope, net) fanout seeds."""
    rows_by_path = {r.full_path: r for r in rows}
    origins: List[Tuple[str, str, str]] = []
    errors: List[str] = []
    for spec in specs:
        text = str(spec).strip()
        if not text:
            errors.append("fanout origin must be non-empty")
            continue
        ep, ep_errs = resolve_endpoint(
            text,
            rows,
            index,
            top=top,
            require_port=False,
            rows_by_path=rows_by_path,
        )
        errors.extend(ep_errs)
        if ep_errs:
            continue
        row = rows_by_path.get(ep.inst_path)
        if row is None:
            errors.append(f"hierarchy not found: {ep.inst_path}")
            continue
        if _is_inst_spec(text, ep, rows_by_path):
            ports = _ports_for_instance(index, row, top)
            if not ports:
                errors.append(f"no ports for instance origin {text}")
                continue
            for port_name, port_dir in ports:
                label = f"{ep.inst_path}.{port_name}"
                if port_dir in ("output", "inout"):
                    origins.append((label, ep.inst_path, port_name))
                elif port_dir == "input":
                    origins.append((label, ep.inst_path, port_name))
            continue
        origins.append((text, ep.inst_path, ep.port_name or ""))
    return origins, errors


def _waypoint_hit(
    scope: str,
    net: str,
    waypoints: WaypointSet,
) -> bool:
    if (scope, net) in waypoints.port_nets:
        return True
    for prefix in waypoints.inst_prefixes:
        if scope == prefix or scope.startswith(prefix + "."):
            return True
    return False


def _ff_net_line(mod_idx, net: str) -> int:
    comb = mod_idx.comb
    rep = net_representative(comb, net)
    return comb.ff_net_lines.get(net, comb.ff_net_lines.get(rep, 0))


def _rtl_line_for_edge(
    ctx: _ConeCtx,
    from_scope: str,
    from_net: str,
    to_scope: str,
    to_net: str,
    event_kind: str,
    inst_leaf: str = "",
) -> int:
    if event_kind in ("ff-interior", "ff-sink", "ff-driver"):
        for scope, net in ((from_scope, from_net), (to_scope, to_net)):
            row = ctx.rows_by_path.get(scope)
            if row is None:
                continue
            mod_idx = _cached_cone_mod(ctx, row)
            line = _ff_net_line(mod_idx, net)
            if line:
                return line
    if event_kind in ("child-down", "child-hier") and inst_leaf:
        row = ctx.rows_by_path.get(from_scope)
        if row is None:
            return 0
        mod_idx = _cached_cone_mod(ctx, row)
        return mod_idx.comb.inst_stmt_lines.get(inst_leaf, 0)
    scope = from_scope if event_kind != "parent-up" else to_scope
    row = ctx.rows_by_path.get(scope)
    if row is None:
        return 0
    mod_idx = _cached_cone_mod(ctx, row)
    prov = lookup_edge_prov(mod_idx.comb, from_net, to_net)
    return prov.line if prov is not None else 0


def _rtl_line_for_boundary(
    ctx: _ConeCtx,
    scope: str,
    net: str,
    event_kind: str,
) -> int:
    row = ctx.rows_by_path.get(scope)
    if row is None:
        return 0
    mod_idx = _cached_cone_mod(ctx, row)
    if event_kind.startswith("ff-"):
        line = _ff_net_line(mod_idx, net)
        if line:
            return line
    return 0


def _trace_origin_fanout(
    source: str,
    start_scope: str,
    start_net: str,
    *,
    ctx: _ConeCtx,
    waypoints: WaypointSet,
    rows_by_path: Mapping[str, FlatRow],
) -> List[WaypointFanoutEvent]:
    row = rows_by_path.get(start_scope)
    if row is None:
        return []
    start_mod = _cached_cone_mod(ctx, row)
    start = _state_key(start_scope, start_net, start_mod)
    start_qualified = _waypoint_hit(start[0], start[1], waypoints)

    visited: Set[BfsState] = {(start[0], start[1], start_qualified)}
    frontier: List[BfsState] = [(start[0], start[1], start_qualified)]
    events: List[WaypointFanoutEvent] = []

    while frontier:
        next_front: List[BfsState] = []
        for scope, net, qualified in frontier:
            state: NetState = (scope, net)
            boundary = _boundary_at_state(
                ctx,
                state,
                is_origin=(state == start),
            )
            if boundary is not None and state != start:
                hit = _waypoint_hit(scope, net, waypoints)
                qual = qualified or hit
                row_hit = rows_by_path.get(scope)
                events.append(
                    WaypointFanoutEvent(
                        source=source,
                        event_kind=boundary.kind,
                        scope=scope,
                        net=net,
                        rtl_file=row_hit.file if row_hit else "",
                        rtl_line=_rtl_line_for_boundary(
                            ctx, scope, net, boundary.kind
                        ),
                        waypoint_hit=_yn(hit),
                        waypoint_qualified=_yn(qual),
                        is_terminator="Y",
                    )
                )
                continue

            for nxt, kind, detail in _expand_fanout(state, ctx):
                nxt_scope, nxt_net = nxt
                hit = _waypoint_hit(nxt_scope, nxt_net, waypoints)
                qual = qualified or hit
                inst_leaf = ""
                if kind in ("child-down", "child-hier"):
                    parent_row = rows_by_path.get(scope)
                    if parent_row is not None:
                        suffix = nxt_scope[len(scope) + 1 :] if nxt_scope.startswith(scope + ".") else ""
                        inst_leaf = suffix.split(".", 1)[0] if suffix else ""
                rtl_line = _rtl_line_for_edge(
                    ctx,
                    scope,
                    net,
                    nxt_scope,
                    nxt_net,
                    kind,
                    inst_leaf=inst_leaf,
                )
                row_nxt = rows_by_path.get(nxt_scope)
                events.append(
                    WaypointFanoutEvent(
                        source=source,
                        event_kind=kind,
                        scope=nxt_scope,
                        net=nxt_net,
                        rtl_file=row_nxt.file if row_nxt else "",
                        rtl_line=rtl_line,
                        waypoint_hit=_yn(hit),
                        waypoint_qualified=_yn(qual),
                        is_terminator="N",
                    )
                )
                b2 = _boundary_at_state(ctx, nxt, is_origin=False)
                if b2 is not None:
                    term_hit = _waypoint_hit(nxt_scope, nxt_net, waypoints)
                    term_qual = qual or term_hit
                    term_line = _rtl_line_for_boundary(
                        ctx, nxt_scope, nxt_net, b2.kind
                    )
                    if not term_line:
                        term_line = rtl_line
                    events.append(
                        WaypointFanoutEvent(
                            source=source,
                            event_kind=b2.kind,
                            scope=nxt_scope,
                            net=nxt_net,
                            rtl_file=row_nxt.file if row_nxt else "",
                            rtl_line=term_line,
                            waypoint_hit=_yn(term_hit),
                            waypoint_qualified=_yn(term_qual),
                            is_terminator="Y",
                        )
                    )
                    continue
                key: BfsState = (nxt_scope, nxt_net, qual)
                if key not in visited:
                    visited.add(key)
                    next_front.append(key)
        frontier = next_front
    return events


def run_waypoint_fanout_check(
    a_specs: Sequence[str],
    b_specs: Sequence[str],
    *,
    rows: Sequence[FlatRow],
    index: DesignIndex,
    top: str,
    path_kind: str = "comb",
    defines: Mapping[str, str] | None = None,
    over_approximate_if: bool = True,
    check_id: str = "",
    endpoint_a: str = "",
    endpoint_b: str = "",
) -> Tuple[ConnectResult, List[WaypointFanoutEvent]]:
    rows_by_path = {r.full_path: r for r in rows}
    child_by_parent_leaf = {
        (r.parent_path, r.inst_leaf): r.full_path
        for r in rows
        if r.parent_path
    }
    waypoints, wp_errs = normalize_waypoints(b_specs, rows, index, top)
    origins, origin_errs = expand_fanout_origins(
        a_specs,
        rows=rows,
        index=index,
        top=top,
    )
    errors = list(wp_errs) + list(origin_errs)
    ep_a = ConnectEndpoint(
        spec=endpoint_a or ",".join(a_specs),
        inst_path=origins[0][1] if origins else "",
        port_name=origins[0][2] if origins else "",
    )
    ep_b = ConnectEndpoint(
        spec=endpoint_b or ",".join(b_specs),
        inst_path="",
        port_name="",
    )

    if errors or not origins:
        return (
            ConnectResult(
                ep_a,
                ep_b,
                False,
                "waypoint-fanout",
                errors=errors or ["no fanout origins resolved"],
                check_id=check_id,
                waypoint_events=(),
            ),
            [],
        )

    ctx = _ConeCtx(
        rows_by_path=rows_by_path,
        child_by_parent_leaf=child_by_parent_leaf,
        index=index,
        top=top,
        mod_cache={},
        defines=dict(defines or {}),
        over_approximate_if=over_approximate_if,
        direction="fanout",
        path_kind=path_kind,
    )

    all_events: List[WaypointFanoutEvent] = []
    for source, scope, net in origins:
        all_events.extend(
            _trace_origin_fanout(
                source,
                scope,
                net,
                ctx=ctx,
                waypoints=waypoints,
                rows_by_path=rows_by_path,
            )
        )

    terminators = [e for e in all_events if e.is_terminator == "Y"]
    qualified_terms = [e for e in terminators if e.waypoint_qualified == "Y"]
    unqualified_terms = [e for e in terminators if e.waypoint_qualified != "Y"]
    connected = bool(qualified_terms) and not errors
    note = (
        f"waypoint-fanout origins={len(origins)} events={len(all_events)} "
        f"qualified_terminators={len(qualified_terms)} "
        f"unqualified_terminators={len(unqualified_terms)}"
    )
    return (
        ConnectResult(
            ep_a,
            ep_b,
            connected,
            "waypoint-fanout",
            errors=errors,
            note=note,
            check_id=check_id,
            waypoint_events=tuple(all_events),
        ),
        all_events,
    )


def format_waypoint_fanout_tsv(events: Sequence[WaypointFanoutEvent]) -> str:
    lines = [
        "source\tevent_kind\tscope\tnet\trtl_file\trtl_line\t"
        "waypoint_hit\twaypoint_qualified\tis_terminator",
    ]
    for ev in events:
        lines.append(
            f"{ev.source}\t{ev.event_kind}\t{ev.scope}\t{ev.net}\t"
            f"{ev.rtl_file}\t{ev.rtl_line}\t"
            f"{ev.waypoint_hit}\t{ev.waypoint_qualified}\t{ev.is_terminator}"
        )
    return "\n".join(lines) + "\n"