"""Expand packed/unpacked port array dimensions into queryable port names."""

from __future__ import annotations

import re
from itertools import product
from typing import Iterable, List, Sequence

from hch.schema import PortRecord

_DIM_RE = re.compile(r"\[([^\]]+)\]")
_DEFAULT_MAX_EXPAND = 512


def parse_dim_bounds(spec: str) -> tuple[int, int]:
    """Parse ``3``, ``2:0``, or ``5:1`` into (high, low) indices."""
    text = spec.strip()
    if ":" in text:
        hi_s, lo_s = text.split(":", 1)
        return int(hi_s.strip()), int(lo_s.strip())
    value = int(text.strip())
    return value, 0


def indices_for_bounds(high: int, low: int) -> List[int]:
    if high >= low:
        return list(range(high, low - 1, -1))
    return list(range(high, low + 1))


def _parse_dimension_specs(width: str) -> List[tuple[int, int]]:
    specs: List[tuple[int, int]] = []
    for match in _DIM_RE.findall(width or ""):
        specs.append(parse_dim_bounds(match))
    return specs


def expand_port_name(
    base: str,
    width: str = "",
    *,
    max_expand: int = _DEFAULT_MAX_EXPAND,
) -> List[str]:
    """
    Materialize port names for indexing/DQL.

    ``data`` + ``[2:0]`` → ``data[2]``, ``data[1]``, ``data[0]``, ``data[2:0]``
    ``sel`` + ``[5:1]`` → ``sel[5]``…``sel[1]``, ``sel[5:1]``
    """
    base = (base or "").strip()
    if not base:
        return []
    specs = _parse_dimension_specs(width)
    if not specs:
        return [base]

    index_lists: List[List[int]] = []
    for hi, lo in specs:
        idxs = indices_for_bounds(hi, lo)
        if len(idxs) > max_expand:
            idxs = idxs[:max_expand]
        index_lists.append(idxs)

    out: List[str] = []
    seen: set[str] = set()

    def add(name: str) -> None:
        if name and name not in seen:
            seen.add(name)
            out.append(name)

    def walk(dim_no: int, prefix: str) -> None:
        if dim_no >= len(index_lists):
            add(prefix)
            return
        hi, lo = specs[dim_no]
        for idx in index_lists[dim_no]:
            walk(dim_no + 1, f"{prefix}[{idx}]")

    walk(0, base)

    for fixed_dims in range(len(specs)):
        prefix_lists = index_lists[:fixed_dims]
        combos = [()] if not prefix_lists else product(*prefix_lists)
        for prefix_indices in combos:
            alias = base
            for idx in prefix_indices:
                alias += f"[{idx}]"
            for dim_no in range(fixed_dims, len(specs)):
                hi, lo = specs[dim_no]
                alias += f"[{hi}:{lo}]"
            add(alias)

    return out


def materialized_port_names(
    ports: Sequence[PortRecord],
    *,
    max_expand: int = _DEFAULT_MAX_EXPAND,
) -> List[str]:
    names: List[str] = []
    seen: set[str] = set()
    for port in ports:
        for name in expand_port_name(port.name, port.width, max_expand=max_expand):
            if name not in seen:
                seen.add(name)
                names.append(name)
    return names


def extract_width_from_port_text(port_text: str, port_name: str) -> str:
    """Pull ``[N]`` / ``[H:L]`` suffixes from a port declaration string."""
    text = (port_text or "").strip()
    name = (port_name or "").strip()
    if name and text.endswith(name):
        text = text[: -len(name)].strip()
    dims = _DIM_RE.findall(text)
    if not dims:
        return ""
    return "".join(f"[{spec}]" for spec in dims)