"""Structural COI connectivity via bidirectional search on hierarchy nets."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, FrozenSet, IO, List, Mapping, Optional, Sequence, Set, Tuple, Union

from scan_inst.connect_request import (
    ConnectivityCheck,
    ConnectivityRequest,
    load_connect_request,
    parse_connect_request_json,
)
from scan_inst.connect_scan import (
    ModuleConnectIndex,
    apply_bind_connectivity,
    apply_empty_module_passthrough,
    build_module_connect_index,
    collect_bind_records_for_module,
    collect_design_defines,
    net_representative,
)
from scan_inst.index import DesignIndex
from scan_inst.models import ConnectEndpoint, ConnectHop, ConnectResult, FlatRow
from scan_inst.params import resolve_param_map
from scan_inst.path_refine import refine_param_ctx_for_path
from scan_inst.port_scan import matching_ports, port_index_for_module, ports_for_module


NetState = Tuple[str, str]
PrevStep = Tuple[NetState, str, str]


@dataclass(frozen=True)
class _ExpandEdge:
    state: NetState
    kind: str
    detail: str


def _net_label(scope: str, net: str) -> str:
    return f"{scope}:{net}" if net else scope


@dataclass
class _SearchCtx:
    rows_by_path: Dict[str, FlatRow]
    child_by_parent_leaf: Dict[Tuple[str, str], str]
    depth_by_path: Dict[str, int]
    index: DesignIndex
    top: str
    mod_cache: Dict[Tuple[str, str], ModuleConnectIndex]
    goal_scope: str
    goal_rep: str
    goal_scope_only: bool
    defines: Mapping[str, str] = field(default_factory=dict)
    param_ctx_cache: Dict[str, Mapping[str, str]] = field(default_factory=dict)
    over_approximate_if: bool = True
    ff_barrier: bool = False


def parse_connect_endpoint(
    spec: str,
    rows_by_path: Mapping[str, FlatRow],
    *,
    index: Optional[DesignIndex] = None,
    top: str = "",
) -> Tuple[str, Optional[str]]:
    text = spec.strip()
    if text in rows_by_path:
        return text, None
    parts = text.split(".")
    for i in range(1, len(parts)):
        prefix = ".".join(parts[:i])
        if prefix not in rows_by_path:
            return prefix, None
    for i in range(len(parts) - 1, 0, -1):
        hier = ".".join(parts[:i])
        row = rows_by_path.get(hier)
        if row is None:
            continue
        port = ".".join(parts[i:])
        if index is not None and _port_exists(index, row, port, top=top):
            return hier, port
    return text, None


def _port_param_ctx(index: DesignIndex, row: FlatRow, top: str) -> Mapping[str, str]:
    if top:
        refined = refine_param_ctx_for_path(index, top, row.full_path)
        if refined.ok and refined.param_ctx:
            return refined.param_ctx
    if row.param_ctx:
        return row.param_ctx
    rec = index.get_module(row.module)
    if not rec:
        return {}
    return resolve_param_map(rec.raw_params)


def _cached_param_ctx(ctx: _SearchCtx, row: FlatRow) -> Mapping[str, str]:
    hit = ctx.param_ctx_cache.get(row.full_path)
    if hit is not None:
        return hit
    pmap = _port_param_ctx(ctx.index, row, ctx.top)
    ctx.param_ctx_cache[row.full_path] = pmap
    return pmap


def _port_exists(
    index: DesignIndex,
    row: FlatRow,
    port_name: str,
    *,
    top: str,
) -> bool:
    ctx = _port_param_ctx(index, row, top)
    port_index = port_index_for_module(row.file, row.module, ctx)
    return bool(matching_ports(port_index, port_name, param_ctx=ctx))


def _nearest_hierarchy_row(
    spec: str,
    rows_by_path: Mapping[str, FlatRow],
) -> Tuple[str, Optional[FlatRow]]:
    text = spec.strip()
    if text in rows_by_path:
        return text, rows_by_path[text]
    parts = text.split(".")
    for i in range(len(parts) - 1, 0, -1):
        prefix = ".".join(parts[:i])
        row = rows_by_path.get(prefix)
        if row is not None:
            return prefix, row
    return "", None


def _child_instances(
    parent_path: str,
    rows_by_path: Mapping[str, FlatRow],
    *,
    limit: int = 12,
) -> List[str]:
    kids = sorted(
        r.inst_leaf
        for r in rows_by_path.values()
        if r.parent_path == parent_path
    )
    return kids[:limit]


def _suggest_instances(
    needle: str,
    children: Sequence[str],
    *,
    limit: int = 8,
) -> List[str]:
    base = needle.split("[", 1)[0]
    out: List[str] = []
    for name in children:
        if base in name or name.startswith(base[: max(1, len(base) // 2)]):
            out.append(name)
    return out[:limit]


def _explain_hierarchy_miss(
    spec: str,
    rows_by_path: Mapping[str, FlatRow],
    *,
    index: DesignIndex,
    top: str,
    broken_prefix: str,
) -> List[str]:
    errors: List[str] = []
    text = spec.strip()
    nearest, row = _nearest_hierarchy_row(text, rows_by_path)

    if row is None:
        roots = sorted({p.split(".", 1)[0] for p in rows_by_path})
        errors.append(f"hierarchy not found: '{text}' — no matching instance path")
        if broken_prefix:
            errors.append(f"missing instance prefix: '{broken_prefix}'")
        if roots:
            errors.append(f"elab roots ({len(roots)}): {', '.join(roots[:8])}")
        return errors

    remainder = text[len(nearest) + 1 :] if len(nearest) < len(text) else ""
    errors.append(
        f"hierarchy not found: '{text}' — path stops at '{nearest}' "
        f"(module {row.module})"
    )
    if remainder:
        errors.append(f"unresolved suffix: '{remainder}'")
    children = _child_instances(nearest, rows_by_path)
    if children:
        errors.append(f"instances under '{nearest}': {', '.join(children)}")
        first_seg = remainder.split(".", 1)[0] if remainder else ""
        similar = _suggest_instances(first_seg, children)
        if similar:
            errors.append(f"similar instance names: {', '.join(similar)}")

    if remainder and "." not in remainder:
        ctx = _port_param_ctx(index, row, top)
        ports = sorted(ports_for_module(row.file, row.module, ctx))
        if ports:
            errors.append(
                f"ports on '{nearest}' ({row.module}, {len(ports)}): "
                f"{', '.join(ports[:16])}"
            )
            leaf = remainder.split("[", 1)[0]
            port_hits = [p for p in ports if leaf in p or p.startswith(leaf)]
            if port_hits:
                errors.append(f"similar port names: {', '.join(port_hits[:8])}")
    return errors


def _explain_port_miss(
    inst_path: str,
    port_name: str,
    row: FlatRow,
    *,
    index: DesignIndex,
    top: str,
) -> List[str]:
    ctx = _port_param_ctx(index, row, top)
    ports = sorted(ports_for_module(row.file, row.module, ctx))
    errors = [
        f"port not found: '{inst_path}.{port_name}' on module {row.module} "
        f"({row.file})"
    ]
    if ports:
        errors.append(f"declared ports ({len(ports)}): {', '.join(ports[:20])}")
        leaf = port_name.split("[", 1)[0].split(".", 1)[0]
        hits = [p for p in ports if leaf in p or p.startswith(leaf)]
        if hits:
            errors.append(f"similar ports: {', '.join(hits[:8])}")
    else:
        errors.append("no ports parsed for this module (blackbox or parse limit)")
    return errors


def resolve_endpoint(
    spec: str,
    rows: Sequence[FlatRow],
    index: DesignIndex,
    *,
    top: str,
    require_port: bool = False,
) -> Tuple[ConnectEndpoint, List[str]]:
    rows_by_path = {r.full_path: r for r in rows}
    text = spec.strip()
    inst_path, port_name = parse_connect_endpoint(
        text,
        rows_by_path,
        index=index,
        top=top,
    )
    errors: List[str] = []
    row = rows_by_path.get(inst_path) if inst_path else None

    if row is None:
        broken = inst_path or text
        errors.extend(
            _explain_hierarchy_miss(
                text,
                rows_by_path,
                index=index,
                top=top,
                broken_prefix=broken,
            )
        )
        return ConnectEndpoint(
            spec=text,
            inst_path=inst_path or "",
            port_name=port_name or "",
            module="",
            port_found=False,
        ), errors

    if port_name is None and text not in rows_by_path:
        suffix = text[len(inst_path) + 1 :] if text.startswith(inst_path + ".") else ""
        if suffix:
            errors.extend(
                _explain_hierarchy_miss(
                    text,
                    rows_by_path,
                    index=index,
                    top=top,
                    broken_prefix=inst_path,
                )
            )
            return ConnectEndpoint(
                spec=text,
                inst_path=inst_path,
                port_name="",
                module=row.module,
                port_found=False,
            ), errors

    ep = ConnectEndpoint(
        spec=text,
        inst_path=inst_path,
        port_name=port_name or "",
        module=row.module,
        port_found=False,
    )
    if port_name is None:
        if require_port:
            errors.append(f"port required but not given: {spec}")
        return ep, errors
    if _port_exists(index, row, port_name, top=top):
        ep.port_found = True
    else:
        errors.extend(_explain_port_miss(inst_path, port_name, row, index=index, top=top))
    return ep, errors


def _lca(path_a: str, path_b: str) -> str:
    parts_a = path_a.split(".")
    parts_b = path_b.split(".")
    common: List[str] = []
    for a, b in zip(parts_a, parts_b):
        if a != b:
            break
        common.append(a)
    return ".".join(common)


def _prune_rows_lca(rows: Sequence[FlatRow], path_a: str, path_b: str) -> List[FlatRow]:
    lca = _lca(path_a, path_b)
    if not lca:
        return list(rows)
    child_prefix = lca + "."
    return [
        r
        for r in rows
        if r.full_path == lca or r.full_path.startswith(child_prefix)
    ]


def _empty_module_passthrough_ports(
    index: DesignIndex,
    mod_name: str,
    param_ctx: Mapping[str, str],
) -> Optional[Tuple[str, str]]:
    rec = index.get_module(mod_name)
    if not rec or not rec.file_path:
        return None
    from pathlib import Path

    from scan_inst.port_scan import scan_ports_detail_from_module_text

    try:
        text = Path(rec.file_path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    inputs: List[str] = []
    outputs: List[str] = []
    for info in scan_ports_detail_from_module_text(
        text, mod_name, param_ctx=param_ctx
    ):
        decl = info.decl.lower()
        if decl.startswith("input"):
            inputs.extend(info.names)
        elif decl.startswith("output"):
            outputs.extend(info.names)
    if len(inputs) == 1 and len(outputs) == 1:
        return inputs[0], outputs[0]
    return None


def _module_index(
    cache: Dict[Tuple[str, str], ModuleConnectIndex],
    index: DesignIndex,
    mod_name: str,
    param_ctx: Mapping[str, str],
    defines: Mapping[str, str] | None = None,
    over_approximate_if: bool = True,
    ff_barrier: bool = False,
) -> ModuleConnectIndex:
    ctx_key = "|".join(f"{k}={v}" for k, v in sorted(param_ctx.items()))
    key = (mod_name, ctx_key)
    hit = cache.get(key)
    if hit is not None:
        return hit
    rec = index.get_module(mod_name)
    body = index.module_body(mod_name) if rec else ""
    if not body.strip():
        built = ModuleConnectIndex()
        passthrough = _empty_module_passthrough_ports(index, mod_name, param_ctx)
        if passthrough:
            apply_empty_module_passthrough(built, passthrough[0], passthrough[1])
    else:
        built = build_module_connect_index(
            body,
            param_map=param_ctx,
            defines=defines,
            fold_generate=True,
            over_approximate_if=over_approximate_if,
            ff_barrier=ff_barrier,
        )
        binds = collect_bind_records_for_module(index, mod_name)
        if binds:
            apply_bind_connectivity(
                built,
                binds,
                index,
                param_map=param_ctx,
                defines=defines,
                over_approximate_if=over_approximate_if,
            )
    cache[key] = built
    return built


def _build_search_ctx(
    rows: Sequence[FlatRow],
    index: DesignIndex,
    top: str,
    goal: NetState,
    *,
    goal_scope_only: bool,
    mod_cache: Dict[Tuple[str, str], ModuleConnectIndex],
    defines: Mapping[str, str] | None = None,
    param_ctx_cache: Optional[Dict[str, Mapping[str, str]]] = None,
    over_approximate_if: bool = True,
    ff_barrier: bool = False,
) -> _SearchCtx:
    rows_by_path = {r.full_path: r for r in rows}
    child_by_parent_leaf: Dict[Tuple[str, str], str] = {}
    depth_by_path: Dict[str, int] = {}
    for row in rows:
        depth_by_path[row.full_path] = row.depth
        if row.parent_path:
            child_by_parent_leaf[(row.parent_path, row.inst_leaf)] = row.full_path
    goal_scope, goal_net = goal
    goal_mod = rows_by_path.get(goal_scope)
    goal_rep = goal_net
    if goal_mod and goal_net:
        gctx = _port_param_ctx(index, goal_mod, top)
        gidx = _module_index(
            mod_cache,
            index,
            goal_mod.module,
            gctx,
            defines=defines,
            over_approximate_if=over_approximate_if,
            ff_barrier=ff_barrier,
        )
        goal_rep = net_representative(gidx, goal_net)
    return _SearchCtx(
        rows_by_path=rows_by_path,
        child_by_parent_leaf=child_by_parent_leaf,
        depth_by_path=depth_by_path,
        index=index,
        top=top,
        mod_cache=mod_cache,
        goal_scope=goal_scope,
        goal_rep=goal_rep,
        goal_scope_only=goal_scope_only,
        defines=dict(defines or {}),
        param_ctx_cache=(
            param_ctx_cache
            if param_ctx_cache is not None
            else {}
        ),
        over_approximate_if=over_approximate_if,
        ff_barrier=ff_barrier,
    )


def _tree_distance(ctx: _SearchCtx, scope_a: str, scope_b: str) -> int:
    if scope_a == scope_b:
        return 0
    da = ctx.depth_by_path.get(scope_a)
    db = ctx.depth_by_path.get(scope_b)
    if da is None or db is None:
        return 10_000
    parts_a = scope_a.split(".")
    parts_b = scope_b.split(".")
    common = 0
    for x, y in zip(parts_a, parts_b):
        if x != y:
            break
        common += 1
    return da + db - 2 * common


def _state_key(
    scope: str,
    net: str,
    mod_idx: ModuleConnectIndex,
) -> NetState:
    return scope, net_representative(mod_idx, net)


def _goal_match(ctx: _SearchCtx, state: NetState) -> bool:
    scope, rep = state
    if ctx.goal_scope_only:
        return scope == ctx.goal_scope
    return scope == ctx.goal_scope and rep == ctx.goal_rep


def _expand_state(
    state: NetState,
    ctx: _SearchCtx,
) -> List[_ExpandEdge]:
    scope, net = state
    row = ctx.rows_by_path.get(scope)
    if row is None:
        return []
    mod_ctx = _cached_param_ctx(ctx, row)
    mod_idx = _module_index(
        ctx.mod_cache,
        ctx.index,
        row.module,
        mod_ctx,
        defines=ctx.defines,
        over_approximate_if=ctx.over_approximate_if,
        ff_barrier=ctx.ff_barrier,
    )
    rep = net_representative(mod_idx, net)

    out: List[_ExpandEdge] = []
    seen_local: Set[NetState] = set()

    def push(
        nxt_scope: str,
        nxt_net: str,
        *,
        kind: str,
        detail: str,
        target_mod_idx: Optional[ModuleConnectIndex] = None,
    ) -> None:
        idx = target_mod_idx or mod_idx
        key = _state_key(nxt_scope, nxt_net, idx)
        if key not in seen_local:
            seen_local.add(key)
            out.append(_ExpandEdge(key, kind, detail))

    here = _net_label(scope, net)
    mod_name = row.module

    for peer_rep in mod_idx.rep_adj.get(rep, ()):
        push(
            scope,
            peer_rep,
            kind="intra-module",
            detail=(
                f"{here} ~ {_net_label(scope, peer_rep)} "
                f"(assign/alias/ff in module {mod_name})"
            ),
        )

    for inst_leaf, port in mod_idx.net_to_children.get(rep, ()):
        child_path = ctx.child_by_parent_leaf.get((scope, inst_leaf))
        if not child_path:
            continue
        child_row = ctx.rows_by_path.get(child_path)
        if child_row is None:
            continue
        child_ctx = _cached_param_ctx(ctx, child_row)
        child_idx = _module_index(
            ctx.mod_cache,
            ctx.index,
            child_row.module,
            child_ctx,
            defines=ctx.defines,
            over_approximate_if=ctx.over_approximate_if,
            ff_barrier=ctx.ff_barrier,
        )
        push(
            child_path,
            port,
            kind="child-down",
            detail=(
                f"{here} -> {_net_label(child_path, port)} "
                f"(instance {inst_leaf} port .{port} in {mod_name})"
            ),
            target_mod_idx=child_idx,
        )

    for inst_leaf, port in mod_idx.hier_links.get(rep, ()):
        child_path = ctx.child_by_parent_leaf.get((scope, inst_leaf))
        if not child_path:
            continue
        child_row = ctx.rows_by_path.get(child_path)
        if child_row is None:
            continue
        child_rec = ctx.index.get_module(child_row.module)
        if child_rec is not None and child_rec.is_interface:
            continue
        child_ctx = _cached_param_ctx(ctx, child_row)
        child_idx = _module_index(
            ctx.mod_cache,
            ctx.index,
            child_row.module,
            child_ctx,
            defines=ctx.defines,
            over_approximate_if=ctx.over_approximate_if,
            ff_barrier=ctx.ff_barrier,
        )
        push(
            child_path,
            port,
            kind="child-hier",
            detail=(
                f"{here} -> {_net_label(child_path, port)} "
                f"(hier ref {inst_leaf}.{port} in {mod_name})"
            ),
            target_mod_idx=child_idx,
        )

    parent_path = row.parent_path
    if parent_path:
        parent_row = ctx.rows_by_path.get(parent_path)
        if parent_row is not None:
            parent_ctx = _cached_param_ctx(ctx, parent_row)
            parent_idx = _module_index(
                ctx.mod_cache,
                ctx.index,
                parent_row.module,
                parent_ctx,
                defines=ctx.defines,
                over_approximate_if=ctx.over_approximate_if,
                ff_barrier=ctx.ff_barrier,
            )
            for port_name, expr in parent_idx.inst_ports.get(row.inst_leaf, ()):
                if net_representative(mod_idx, port_name) != rep:
                    continue
                roots: FrozenSet[str] = parent_idx.expr_roots.get(expr) or frozenset()
                child_lbl = _net_label(scope, port_name)
                if not roots and expr.strip():
                    push(
                        parent_path,
                        expr.strip(),
                        kind="parent-up",
                        detail=(
                            f"{child_lbl} -> {_net_label(parent_path, expr.strip())} "
                            f"(port map {row.inst_leaf}.{port_name} = {expr} "
                            f"in parent {parent_row.module})"
                        ),
                        target_mod_idx=parent_idx,
                    )
                for root in roots:
                    push(
                        parent_path,
                        root,
                        kind="parent-up",
                        detail=(
                            f"{child_lbl} -> {_net_label(parent_path, root)} "
                            f"(port map {row.inst_leaf}.{port_name} = {expr} "
                            f"in parent {parent_row.module})"
                        ),
                        target_mod_idx=parent_idx,
                    )
            cur_rec = ctx.index.get_module(row.module)
            skip_iface_hier = cur_rec is not None and cur_rec.is_interface
            for (inst_leaf, port), parent_reps in parent_idx.hier_ref_targets.items():
                if inst_leaf != row.inst_leaf:
                    continue
                if net_representative(mod_idx, port) != rep:
                    continue
                if skip_iface_hier:
                    continue
                child_lbl = _net_label(scope, port)
                for parent_net in parent_reps:
                    push(
                        parent_path,
                        parent_net,
                        kind="parent-hier-ref",
                        detail=(
                            f"{child_lbl} -> {_net_label(parent_path, parent_net)} "
                            f"(parent hier ref to {inst_leaf}.{port} "
                            f"in {parent_row.module})"
                        ),
                        target_mod_idx=parent_idx,
                    )

    out.sort(key=lambda e: _tree_distance(ctx, e.state[0], ctx.goal_scope))
    return out


def _meet(
    front_a: Set[NetState],
    seen_b: Set[NetState],
    ctx: _SearchCtx,
) -> Optional[NetState]:
    for state in front_a:
        if state in seen_b:
            return state
        if ctx.goal_scope_only and state[0] == ctx.goal_scope:
            return state
    return None


def _meet_seen(
    seen_a: Set[NetState],
    seen_b: Set[NetState],
) -> Optional[NetState]:
    both = seen_a & seen_b
    if not both:
        return None
    return min(both, key=lambda s: (len(s[0]), s[0], s[1]))


def _connect_note(ok: bool, modules_parsed: int, *, hier: bool = False) -> str:
    suffix = f"; {modules_parsed} module(s)"
    if hier:
        return ("reaches hierarchy" if ok else "does not reach hierarchy") + suffix
    return ("connected" if ok else "no path") + suffix


def _resolve_over_approximate_if(
    strict_generate: bool,
    over_approximate_if: Optional[bool],
) -> bool:
    if over_approximate_if is not None:
        return over_approximate_if
    return not strict_generate


def _bidirectional_coi(
    start: NetState,
    goal: NetState,
    *,
    rows: Sequence[FlatRow],
    index: DesignIndex,
    top: str,
    defines: Mapping[str, str] | None = None,
    goal_scope_only: bool = False,
    trace: bool = False,
    strict_generate: bool = False,
    ff_barrier: bool = False,
    over_approximate_if: Optional[bool] = None,
    mod_cache: Optional[Dict[Tuple[str, str], ModuleConnectIndex]] = None,
    param_ctx_cache: Optional[Dict[str, Mapping[str, str]]] = None,
) -> Tuple[bool, List[ConnectHop], int]:
    over_approx = _resolve_over_approximate_if(strict_generate, over_approximate_if)
    cache = mod_cache if mod_cache is not None else {}
    ctx = _build_search_ctx(
        rows,
        index,
        top,
        goal,
        goal_scope_only=goal_scope_only,
        mod_cache=cache,
        defines=defines,
        param_ctx_cache=param_ctx_cache,
        over_approximate_if=over_approx,
        ff_barrier=ff_barrier,
    )

    start_row = ctx.rows_by_path.get(start[0])
    if start_row is None:
        return False, [], 0
    start_ctx = _cached_param_ctx(ctx, start_row)
    start_idx = _module_index(
        cache,
        index,
        start_row.module,
        start_ctx,
        defines=defines,
        over_approximate_if=over_approx,
        ff_barrier=ff_barrier,
    )
    start_key = _state_key(start[0], start[1], start_idx)

    if _goal_match(ctx, start_key):
        return True, [], len(cache)

    if goal_scope_only:
        goal_key = (goal[0], "")
    else:
        goal_row = ctx.rows_by_path.get(goal[0])
        if goal_row is None:
            return False, [], len(cache)
        goal_ctx = _cached_param_ctx(ctx, goal_row)
        goal_idx = _module_index(
            cache,
            index,
            goal_row.module,
            goal_ctx,
            defines=defines,
            over_approximate_if=over_approx,
            ff_barrier=ff_barrier,
        )
        goal_key = _state_key(goal[0], goal[1], goal_idx)

    seen_f: Set[NetState] = {start_key}
    seen_b: Set[NetState] = {goal_key}
    front_f: Set[NetState] = {start_key}
    front_b: Set[NetState] = {goal_key}
    prev_f: Dict[NetState, PrevStep] = {}
    prev_b: Dict[NetState, PrevStep] = {}

    def expand_frontier(
        frontier: Set[NetState],
        seen: Set[NetState],
        prev: Dict[NetState, PrevStep],
        other_seen: Set[NetState],
        toward_scope: str,
    ) -> Set[NetState]:
        ordered: List[Tuple[int, int, NetState]] = []
        for state in frontier:
            h = _tree_distance(ctx, state[0], toward_scope)
            ordered.append((h, len(state[0]), state))
        ordered.sort()

        next_front: Set[NetState] = set()
        for _, _, state in ordered:
            for edge in _expand_state(state, ctx):
                nxt = edge.state
                if nxt in seen:
                    continue
                seen.add(nxt)
                prev[nxt] = (state, edge.kind, edge.detail)
                if nxt in other_seen:
                    return {nxt}
                next_front.add(nxt)
        return next_front

    mod_n = len(cache)

    def _done(ok: bool, hops: List[ConnectHop]) -> Tuple[bool, List[ConnectHop], int]:
        return ok, hops, len(cache)

    while front_f or front_b:
        hit = _meet(front_f, seen_b, ctx)
        if hit is not None:
            return _done(
                True,
                _reconstruct_bidirectional(hit, prev_f, prev_b, start_key, goal_key, trace),
            )
        hit = _meet(front_b, seen_f, ctx)
        if hit is not None:
            return _done(
                True,
                _reconstruct_bidirectional(hit, prev_f, prev_b, start_key, goal_key, trace),
            )

        if front_f and (not front_b or len(front_f) <= len(front_b)):
            nxt = expand_frontier(front_f, seen_f, prev_f, seen_b, ctx.goal_scope)
            if len(nxt) == 1 and next(iter(nxt)) in seen_b:
                hit = next(iter(nxt))
                return _done(
                    True,
                    _reconstruct_bidirectional(
                        hit, prev_f, prev_b, start_key, goal_key, trace
                    ),
                )
            front_f = nxt
        elif front_b:
            nxt = expand_frontier(front_b, seen_b, prev_b, seen_f, start[0])
            if len(nxt) == 1 and next(iter(nxt)) in seen_f:
                hit = next(iter(nxt))
                return _done(
                    True,
                    _reconstruct_bidirectional(
                        hit, prev_f, prev_b, start_key, goal_key, trace
                    ),
                )
            front_b = nxt
        else:
            break

    hit = _meet_seen(seen_f, seen_b)
    if hit is not None:
        return _done(
            True,
            _reconstruct_bidirectional(hit, prev_f, prev_b, start_key, goal_key, trace),
        )

    return False, [], len(cache)


def _forward_coi_to_scope(
    start: NetState,
    goal_scope: str,
    *,
    rows: Sequence[FlatRow],
    index: DesignIndex,
    top: str,
    defines: Mapping[str, str] | None = None,
    trace: bool = False,
    strict_generate: bool = False,
    ff_barrier: bool = False,
    over_approximate_if: Optional[bool] = None,
    mod_cache: Optional[Dict[Tuple[str, str], ModuleConnectIndex]] = None,
    param_ctx_cache: Optional[Dict[str, Mapping[str, str]]] = None,
) -> Tuple[bool, List[ConnectHop], int]:
    over_approx = _resolve_over_approximate_if(strict_generate, over_approximate_if)
    cache = mod_cache if mod_cache is not None else {}
    ctx = _build_search_ctx(
        rows,
        index,
        top,
        (goal_scope, ""),
        goal_scope_only=True,
        mod_cache=cache,
        defines=defines,
        param_ctx_cache=param_ctx_cache,
        over_approximate_if=over_approx,
        ff_barrier=ff_barrier,
    )
    start_row = ctx.rows_by_path.get(start[0])
    if start_row is None:
        return False, [], 0
    start_ctx = _cached_param_ctx(ctx, start_row)
    start_idx = _module_index(
        cache,
        index,
        start_row.module,
        start_ctx,
        defines=defines,
        over_approximate_if=over_approx,
        ff_barrier=ff_barrier,
    )
    start_key = _state_key(start[0], start[1], start_idx)
    if start_key[0] == goal_scope:
        return True, [], len(cache)

    seen: Set[NetState] = {start_key}
    front: Set[NetState] = {start_key}
    prev: Dict[NetState, PrevStep] = {}

    while front:
        ordered = sorted(
            front,
            key=lambda s: (_tree_distance(ctx, s[0], goal_scope), len(s[0])),
        )
        next_front: Set[NetState] = set()
        for state in ordered:
            for edge in _expand_state(state, ctx):
                nxt = edge.state
                if nxt in seen:
                    continue
                seen.add(nxt)
                prev[nxt] = (state, edge.kind, edge.detail)
                if nxt[0] == goal_scope:
                    mod_n = len(cache)
                    if trace:
                        hops = _reconstruct_forward(start_key, nxt, prev)
                        return True, hops, mod_n
                    return True, [ConnectHop(kind="coi", detail="structural COI path")], mod_n
                next_front.add(nxt)
        front = next_front
    return False, [], len(cache)


def _reconstruct_forward(
    start: NetState,
    end: NetState,
    prev: Mapping[NetState, PrevStep],
) -> List[ConnectHop]:
    hops: List[ConnectHop] = []
    cur = end
    while cur != start and cur in prev:
        _, kind, detail = prev[cur]
        hops.append(ConnectHop(kind=kind, detail=detail))
        cur = prev[cur][0]
    hops.reverse()
    return hops


def _reconstruct_bidirectional(
    meet: NetState,
    prev_f: Mapping[NetState, PrevStep],
    prev_b: Mapping[NetState, PrevStep],
    start: NetState,
    goal: NetState,
    trace: bool,
) -> List[ConnectHop]:
    if not trace:
        return [ConnectHop(kind="coi", detail="structural COI path")]
    hops: List[ConnectHop] = []
    cur = meet
    while cur != start and cur in prev_f:
        _, kind, detail = prev_f[cur]
        hops.append(ConnectHop(kind=kind, detail=detail))
        cur = prev_f[cur][0]
    hops.reverse()
    cur = meet
    tail: List[ConnectHop] = []
    while cur != goal and cur in prev_b:
        _, kind, detail = prev_b[cur]
        tail.append(ConnectHop(kind=kind, detail=detail))
        cur = prev_b[cur][0]
    hops.extend(tail)
    return hops


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
) -> ConnectResult:
    ep_a, err_a = resolve_endpoint(endpoint_a, rows, index, top=top, require_port=False)
    ep_b, err_b = resolve_endpoint(endpoint_b, rows, index, top=top, require_port=False)
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

    def __post_init__(self) -> None:
        if not self.top and self.rows:
            self.top = self.rows[0].full_path.split(".", 1)[0]
        self._effective_defines = _effective_defines(self.index, self.defines)

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
        rows_by_path = {r.full_path: r for r in self.rows}
        row = rows_by_path.get(inst_path)
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