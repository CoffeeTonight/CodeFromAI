"""Merge Tier P ``bind`` instances into Tier E flat index rows."""

from __future__ import annotations

from typing import Dict, List, Mapping, Set

from hch.ingest.bind_attach import bind_anchor_relative
from hch.ingest.hierarchy_build import elaborate_flat
from hch.schema import FlatInstance, ModuleRecord


def _is_bind_flat_row(row: FlatInstance, mod_map: Mapping[str, ModuleRecord]) -> bool:
    for rec in mod_map.values():
        for edge in rec.instances:
            if not edge.via_bind:
                continue
            if row.name != edge.inst_name and not row.full_path.endswith(
                "." + edge.inst_name
            ):
                continue
            anchor = bind_anchor_relative(edge.bind_target_hier, edge.parent_module)
            if anchor and anchor in row.full_path:
                return True
            if not anchor and edge.parent_module in row.full_path:
                return True
    return False


def merge_tier_p_bind_instances(
    elab_flat: List[FlatInstance],
    mod_map: Mapping[str, ModuleRecord],
    *,
    top_module: str,
) -> tuple[List[FlatInstance], int]:
    """
    Append Tier P flatten rows for hierarchical ``bind`` not present after elaboration.

    Returns merged flat list and count of rows added.
    """
    if not top_module or top_module not in mod_map:
        return elab_flat, 0
    elab_paths: Set[str] = {f.full_path for f in elab_flat}
    tier_p = elaborate_flat(mod_map, top_module=top_module)
    extra: List[FlatInstance] = []
    for row in tier_p:
        if row.full_path in elab_paths:
            continue
        if _is_bind_flat_row(row, mod_map):
            extra.append(row)
    if not extra:
        return elab_flat, 0
    return list(elab_flat) + extra, len(extra)