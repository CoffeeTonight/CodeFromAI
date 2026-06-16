"""Hierarchy endpoint resolution and per-module connect graphs."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from scan_inst.connect_scan import (
    ModuleConnectIndex,
    apply_bind_connectivity,
    apply_empty_module_passthrough,
    build_module_connect_index,
    collect_bind_records_for_module,
)
from scan_inst.index import DesignIndex
from scan_inst.models import ConnectEndpoint, FlatRow
from scan_inst.params import resolve_param_map
from scan_inst.path_refine import refine_param_ctx_for_path
from scan_inst.port_scan import (
    matching_ports,
    port_index_for_design_module,
    ports_for_module,
    scan_ports_detail_from_module_text,
)


def _port_decl_bit_indices(
    index: DesignIndex,
    mod_name: str,
    param_ctx: Mapping[str, str],
) -> Dict[str, List[int]]:
    rec = index.get_module(mod_name)
    if not rec or not rec.file_path:
        return {}
    try:
        text = Path(rec.file_path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return {}
    out: Dict[str, List[int]] = {}
    for info in scan_ports_detail_from_module_text(
        text,
        mod_name,
        param_ctx=param_ctx,
    ):
        bits: List[int] = []
        for name in info.names:
            m = re.match(rf"^{re.escape(info.base_name)}\[(\d+)\]$", name)
            if m:
                bits.append(int(m.group(1)))
        if bits:
            out[info.base_name] = sorted(set(bits))
    return out

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




def _port_exists(
    index: DesignIndex,
    row: FlatRow,
    port_name: str,
    *,
    top: str,
) -> bool:
    ctx = _port_param_ctx(index, row, top)
    port_index = port_index_for_design_module(index, row.module, ctx)
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
    rows_by_path: Optional[Mapping[str, FlatRow]] = None,
) -> Tuple[ConnectEndpoint, List[str]]:
    lookup = (
        dict(rows_by_path)
        if rows_by_path is not None
        else {r.full_path: r for r in rows}
    )
    text = spec.strip()
    inst_path, port_name = parse_connect_endpoint(
        text,
        lookup,
        index=index,
        top=top,
    )
    errors: List[str] = []
    row = lookup.get(inst_path) if inst_path else None

    if row is None:
        broken = inst_path or text
        errors.extend(
            _explain_hierarchy_miss(
                text,
                lookup,
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

    if port_name is None and text not in lookup:
        suffix = text[len(inst_path) + 1 :] if text.startswith(inst_path + ".") else ""
        if suffix:
            errors.extend(
                _explain_hierarchy_miss(
                    text,
                    lookup,
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
            port_decl_widths=_port_decl_bit_indices(index, mod_name, param_ctx),
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
