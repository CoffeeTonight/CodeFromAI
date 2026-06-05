"""Expand instance array ranges (literal and parameter-resolved)."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Optional

from hch.ingest.generate_unroll import resolve_parameter_expression


def _syntax_text(node: Any) -> str:
    if node is None:
        return ""
    if hasattr(node, "text"):
        return str(node.text)
    if hasattr(node, "valueText"):
        return str(node.valueText)
    return str(node).strip()


def _bounds_from_range_select(sel: Any, param_map: Mapping[str, str]) -> Optional[tuple[int, int]]:
    if sel is None:
        return None
    left = resolve_parameter_expression(getattr(sel, "left", None), param_map)
    right = resolve_parameter_expression(getattr(sel, "right", None), param_map)
    if left is None or right is None:
        return None
    lo, hi = min(left, right), max(left, right)
    return lo, hi


def _bounds_from_dimension(dim: Any, param_map: Mapping[str, str]) -> Optional[tuple[int, int]]:
    if dim is None:
        return None
    spec = getattr(dim, "specifier", None)
    if spec is None:
        return None
    sel = getattr(spec, "selector", None)
    kind = str(getattr(sel, "kind", ""))
    if "Range" in kind or "SimpleRange" in kind:
        return _bounds_from_range_select(sel, param_map)
    return None


def expand_instance_name(
    decl: Any,
    param_map: Optional[Mapping[str, str]] = None,
    *,
    max_width: int = 64,
) -> List[str]:
    """
    Return leaf instance names for *decl* (``InstanceNameSyntax`` or raw string).

    Supports ``u[0:3]`` and ``u[N-1:0]`` when bounds fold from *param_map*.
    """
    pmap = param_map or {}
    if decl is None:
        return []
    kind = str(getattr(decl, "kind", ""))
    if "InstanceName" in kind:
        base = _syntax_text(getattr(decl, "name", None))
        if not base:
            return []
        dims = getattr(decl, "dimensions", None) or []
        if not dims:
            return [base]
        bounds = _bounds_from_dimension(dims[0], pmap)
        if bounds is None:
            raw = f"{base}{_syntax_text(dims[0])}" if dims else base
            return _expand_array_text(raw, pmap, max_width=max_width) or [raw]
        lo, hi = bounds
        if hi - lo + 1 > max_width:
            return [f"{base}[{lo}:{hi}]"]
        return [f"{base}[{i}]" for i in range(lo, hi + 1)]

    raw = str(decl).strip()
    if not raw:
        return []
    return _expand_array_text(raw, pmap, max_width=max_width) or [raw]


def _expand_array_text(
    decl_text: str,
    param_map: Mapping[str, str],
    *,
    max_width: int = 64,
) -> List[str]:
    m = re.match(
        r"^([A-Za-z_]\w*)\s*\[\s*([^\]]+)\s*:\s*([^\]]+)\s*\]\s*$",
        decl_text.strip(),
    )
    if not m:
        return []
    base, lo_t, hi_t = m.group(1), m.group(2).strip(), m.group(3).strip()
    lo = _parse_bound_token(lo_t, param_map)
    hi = _parse_bound_token(hi_t, param_map)
    if lo is None or hi is None:
        return []
    if hi < lo:
        lo, hi = hi, lo
    if hi - lo + 1 > max_width:
        return [f"{base}[{lo}:{hi}]"]
    return [f"{base}[{i}]" for i in range(lo, hi + 1)]


def _parse_bound_token(token: str, param_map: Mapping[str, str]) -> Optional[int]:
    token = token.strip()
    if re.fullmatch(r"-?\d+", token):
        return int(token)
    if token in param_map:
        from hch.ingest.generate_unroll import _param_int

        return _param_int(param_map[token])
    m = re.match(r"^([A-Za-z_]\w*)\s*-\s*(\d+)$", token)
    if m and m.group(1) in param_map:
        from hch.ingest.generate_unroll import _param_int

        base = _param_int(param_map[m.group(1)])
        if base is not None:
            return base - int(m.group(2))
    m = re.match(r"^([A-Za-z_]\w*)\s*\+\s*(\d+)$", token)
    if m and m.group(1) in param_map:
        from hch.ingest.generate_unroll import _param_int

        base = _param_int(param_map[m.group(1)])
        if base is not None:
            return base + int(m.group(2))
    return None