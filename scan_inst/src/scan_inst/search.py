"""Instance / module name search over elaborated hierarchy."""

from __future__ import annotations

import fnmatch
import re
from typing import Dict, Iterable, List, Optional, Sequence, Union

SearchPatterns = Union[str, Sequence[str]]

from scan_inst.models import ElabNode, FlatRow, SearchHit


def parse_search_patterns(raw: str) -> List[str]:
    """Split ``niu,sramc`` or ``\"niu\",\"sramc\"`` into separate patterns."""
    out: List[str] = []
    for chunk in raw.split(","):
        token = chunk.strip().strip('"').strip("'")
        if token:
            out.append(token)
    return out


def normalize_search_patterns(pattern: SearchPatterns) -> List[str]:
    if isinstance(pattern, str):
        text = pattern.strip()
        if not text:
            return []
        if "," in text:
            return parse_search_patterns(text)
        return [text]
    return [p.strip() for p in pattern if str(p).strip()]


def _glob_to_regex(pattern: str) -> str:
    parts: List[str] = []
    for ch in pattern:
        if ch == "*":
            parts.append(".*")
        elif ch == "?":
            parts.append(".")
        else:
            parts.append(re.escape(ch))
    return "".join(parts)


def _segment_glob_match(segment: str, pattern: str) -> bool:
    if any(ch in pattern for ch in "*?[]"):
        if fnmatch.fnmatchcase(segment, pattern):
            return True
        return re.search(_glob_to_regex(pattern), segment, re.IGNORECASE) is not None
    return segment.lower() == pattern.lower()


def _name_match(name: str, pattern: str) -> bool:
    if any(ch in pattern for ch in "*?[]"):
        return fnmatch.fnmatchcase(name, pattern)
    if any(ch in pattern for ch in ".^$+?{}|()\\"):
        return re.compile(pattern, re.IGNORECASE).search(name) is not None
    return pattern.lower() in name.lower()


def _uses_path_pattern(pattern: str) -> bool:
    return "." in pattern


def path_pattern_match(full_path: str, pattern: str) -> bool:
    """
    Match hierarchy paths.

    - ``*niu*`` — any path segment matches (ordered subsequence).
    - ``*ab.*c*.asd*`` — dot splits segment globs; each must appear in order.
    - ``soc.ab.c.asd`` — also matches via whole-path ``fnmatch``.
    """
    if not pattern:
        return False
    if fnmatch.fnmatchcase(full_path, pattern):
        return True
    pat_parts = [part for part in pattern.split(".") if part]
    if not pat_parts:
        return False
    path_parts = full_path.split(".")
    pi = 0
    for seg in path_parts:
        if pi >= len(pat_parts):
            break
        if _segment_glob_match(seg, pat_parts[pi]):
            pi += 1
    return pi == len(pat_parts)


def row_matches_search_pattern(
    row: FlatRow,
    pattern: str,
    *,
    match_inst: bool,
    match_module: bool,
) -> bool:
    if match_inst:
        if _uses_path_pattern(pattern):
            if path_pattern_match(row.full_path, pattern):
                return True
        elif _name_match(row.inst_leaf, pattern):
            return True
    if match_module and _name_match(row.module, pattern):
        return True
    return False


def _under_any_prefix(path: str, prefixes: Sequence[str]) -> bool:
    for prefix in prefixes:
        if path == prefix or path.startswith(f"{prefix}."):
            return True
    return False


def hit_from_row(
    row: FlatRow,
    *,
    matched_name: str,
    match_kind: str,
    full_path: Optional[str] = None,
) -> SearchHit:
    return SearchHit(
        full_path=full_path or row.full_path,
        matched_name=matched_name,
        module=row.module,
        depth=row.depth,
        file=row.file,
        match_kind=match_kind,
        stop_reason=row.stop_reason,
        via_filelist=row.via_filelist,
        filelist_chain=row.filelist_chain,
    )


def search_flat_rows(
    rows: Sequence[FlatRow],
    pattern: SearchPatterns,
    *,
    match_inst: bool = True,
    match_module: bool = False,
    include_subtree: bool = False,
) -> List[SearchHit]:
    """
    Search flattened instance rows.

    Each :class:`FlatRow` already carries ``full_path`` (top→leaf). Multiple
    patterns (comma-separated string or sequence) are combined with OR. With
    ``include_subtree``, anchors are instance rows whose ``inst_leaf`` (or
    module type) matches any pattern, then every descendant row under those
    anchors is included.
    """
    patterns = normalize_search_patterns(pattern)
    anchors: set[str] = set()
    anchor_kinds: Dict[str, str] = {}
    for row in rows:
        for pat in patterns:
            if row_matches_search_pattern(
                row, pat, match_inst=match_inst, match_module=match_module
            ):
                anchors.add(row.full_path)
                if match_module and _name_match(row.module, pat):
                    anchor_kinds[row.full_path] = "module"
                else:
                    anchor_kinds[row.full_path] = "instance"
                break

    if not anchors:
        return []

    if not include_subtree:
        hits: List[SearchHit] = []
        for row in rows:
            if row.full_path not in anchors:
                continue
            kind = anchor_kinds[row.full_path]
            matched = row.inst_leaf if kind == "instance" else row.module
            hits.append(hit_from_row(row, matched_name=matched, match_kind=kind))
        hits.sort(key=lambda h: h.full_path)
        return hits

    hits = []
    for row in rows:
        if not _under_any_prefix(row.full_path, sorted(anchors)):
            continue
        if row.full_path in anchors:
            kind = anchor_kinds[row.full_path]
            matched = row.inst_leaf if kind == "instance" else row.module
            hits.append(hit_from_row(row, matched_name=matched, match_kind=kind))
        else:
            hits.append(
                hit_from_row(
                    row,
                    matched_name=row.inst_leaf,
                    match_kind="hierarchy-under",
                )
            )
    hits.sort(key=lambda h: h.full_path)
    return hits


def enrich_hits_from_rows(hits: Sequence[SearchHit], rows: Sequence[FlatRow]) -> List[SearchHit]:
    """Attach filelist provenance using instance path (strip port suffix if any)."""
    by_path = {row.full_path: row for row in rows}
    out: List[SearchHit] = []
    for hit in hits:
        inst_path = hit.full_path
        if hit.port_name and inst_path.endswith(f".{hit.port_name}"):
            inst_path = inst_path[: -(len(hit.port_name) + 1)]
        row = by_path.get(inst_path)
        if row is None:
            out.append(hit)
            continue
        out.append(
            SearchHit(
                full_path=hit.full_path,
                matched_name=hit.matched_name,
                module=hit.module,
                depth=hit.depth,
                file=hit.file or row.file,
                match_kind=hit.match_kind,
                stop_reason=hit.stop_reason or row.stop_reason,
                via_filelist=row.via_filelist,
                filelist_chain=row.filelist_chain,
                port_name=hit.port_name,
                port_found=hit.port_found,
                port_line=hit.port_line,
                port_decl=hit.port_decl,
                port_param_note=hit.port_param_note,
            )
        )
    return out


def search_tree(
    root: ElabNode,
    pattern: str,
    *,
    match_inst: bool = True,
    match_module: bool = False,
) -> List[SearchHit]:
    hits: List[SearchHit] = []

    def walk(node: ElabNode) -> None:
        if match_inst and _name_match(node.inst_name, pattern):
            hits.append(
                SearchHit(
                    full_path=node.full_path,
                    matched_name=node.inst_name,
                    module=node.module,
                    depth=node.full_path.count("."),
                    file=node.file_path,
                    match_kind="instance",
                    stop_reason=node.stop_reason,
                )
            )
        if match_module and _name_match(node.module, pattern):
            hits.append(
                SearchHit(
                    full_path=node.full_path,
                    matched_name=node.module,
                    module=node.module,
                    depth=node.full_path.count("."),
                    file=node.file_path,
                    match_kind="module",
                    stop_reason=node.stop_reason,
                )
            )
        for child in node.children:
            walk(child)

    walk(root)
    return hits


def search(
    pattern: SearchPatterns,
    *,
    rows: Optional[Sequence[FlatRow]] = None,
    root: Optional[ElabNode] = None,
    match_inst: bool = True,
    match_module: bool = False,
    include_subtree: bool = False,
) -> List[SearchHit]:
    patterns = normalize_search_patterns(pattern)
    if rows is not None:
        return search_flat_rows(
            rows,
            patterns,
            match_inst=match_inst,
            match_module=match_module,
            include_subtree=include_subtree,
        )
    if root is not None:
        hits: List[SearchHit] = []
        seen: set[str] = set()
        for pat in patterns:
            for hit in search_tree(
                root,
                pat,
                match_inst=match_inst,
                match_module=match_module,
            ):
                if hit.full_path in seen:
                    continue
                seen.add(hit.full_path)
                hits.append(hit)
        hits.sort(key=lambda h: h.full_path)
        return hits
    return []