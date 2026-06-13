"""Hierarchy path and port search with ``*`` / ``?`` globs."""

from __future__ import annotations

import fnmatch
from typing import List, Mapping, Optional, Sequence, Tuple

from scan_inst.index import DesignIndex
from scan_inst.models import FlatRow, SearchHit
from scan_inst.params import resolve_param_map
from scan_inst.path_chain import attach_path_chains
from scan_inst.path_refine import refine_param_ctx_for_path
from scan_inst.port_scan import matching_ports, port_index_for_module
from scan_inst.search import hit_from_row


def parse_hierarchy_port_pattern(pattern: str) -> Tuple[str, Optional[str]]:
    parts = pattern.split(".")
    if len(parts) >= 3:
        return ".".join(parts[:-1]), parts[-1]
    return pattern, None


def hierarchy_glob_match(path: str, pattern: str) -> bool:
    path_parts = path.split(".")
    pat_parts = pattern.split(".")
    if len(path_parts) != len(pat_parts):
        return False
    for part, glob_part in zip(path_parts, pat_parts):
        if any(ch in glob_part for ch in "*?[]"):
            if not fnmatch.fnmatchcase(part, glob_part):
                return False
        elif part.lower() != glob_part.lower():
            return False
    return True


def _port_param_ctx(index: DesignIndex, row: FlatRow) -> Mapping[str, str]:
    if row.param_ctx:
        return row.param_ctx
    rec = index.get_module(row.module)
    if not rec:
        return {}
    return resolve_param_map(rec.raw_params)


def _top_from_rows(rows: Sequence[FlatRow]) -> str:
    if not rows:
        return ""
    return rows[0].full_path.split(".", 1)[0]


def search_hierarchy_path(
    rows: Sequence[FlatRow],
    pattern: str,
    index: DesignIndex,
    *,
    require_port: bool = True,
    refine_port_ctx: bool = True,
) -> List[SearchHit]:
    inst_pat, port_pat = parse_hierarchy_port_pattern(pattern)
    top = _top_from_rows(rows)
    refine_cache: dict = {}
    hits: List[SearchHit] = []
    for row in rows:
        if not hierarchy_glob_match(row.full_path, inst_pat):
            continue
        if port_pat is None:
            hit = hit_from_row(
                row, matched_name=row.inst_leaf, match_kind="hierarchy"
            )
            hits.append(hit)
            continue
        if not require_port:
            hit = hit_from_row(
                row,
                matched_name=port_pat,
                match_kind="hierarchy-port",
                full_path=f"{row.full_path}.{port_pat}",
            )
            hit.port_name = port_pat
            hits.append(hit)
            continue

        ctx = _port_param_ctx(index, row)
        refine_note = ""
        if refine_port_ctx and top:
            if row.full_path not in refine_cache:
                refine_cache[row.full_path] = refine_param_ctx_for_path(
                    index, top, row.full_path
                )
            refined = refine_cache[row.full_path]
            if refined.ok:
                ctx = refined.param_ctx
                refine_note = refined.note
        port_index = port_index_for_module(row.file, row.module, ctx)
        matched = matching_ports(port_index, port_pat, param_ctx=ctx)
        for port_name in matched:
            info = port_index[port_name]
            hit = hit_from_row(
                row,
                matched_name=port_name,
                match_kind="hierarchy-port",
                full_path=f"{row.full_path}.{port_name}",
            )
            hit.port_name = port_name
            hit.port_found = True
            hit.port_line = info.line
            hit.port_decl = info.decl
            note = info.param_note
            if refine_note and note:
                hit.port_param_note = f"{refine_note}; {note}"
            else:
                hit.port_param_note = refine_note or note
            hits.append(hit)
    return attach_path_chains(
        hits,
        index,
        rows,
        top=top,
        refine_paths=refine_port_ctx,
        refine_cache=refine_cache,
    )