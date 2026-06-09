"""DQL query modifiers stripped before Lark parse."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class QueryModifiers:
    lastnode: bool = False
    expand_ports: bool = False


def extract_query_modifiers(expr: str) -> Tuple[str, QueryModifiers]:
    """Remove modifier keywords. Returns (cleaned_expr, modifiers)."""
    cleaned = expr.strip()
    mods = QueryModifiers()

    def _strip_modifier(text: str, pattern: str) -> str:
        text = re.sub(rf"\s+AND\s+{pattern}", "", text, flags=re.I)
        text = re.sub(rf"{pattern}\s+AND\s+", "", text, flags=re.I)
        text = re.sub(rf"{pattern}", "", text, flags=re.I)
        return text.strip()

    if re.search(r"\blastnode\b", cleaned, re.I):
        mods.lastnode = True
        cleaned = _strip_modifier(cleaned, r"lastnode")

    if re.search(r"\bexpand_ports\b", cleaned, re.I):
        mods.expand_ports = True
        cleaned = _strip_modifier(cleaned, r"expand_ports")

    return cleaned, mods


def apply_lastnode(rows: list) -> list:
    """Keep rows with no other hit as strict descendant in the result set."""
    kept = []
    paths = [r["full_path"] for r in rows]
    for r in rows:
        fp = r["full_path"]
        if any(other != fp and other.startswith(fp + ".") for other in paths):
            continue
        kept.append(r)
    return kept


def _port_names(row: Dict[str, Any]) -> List[str]:
    pj = row.get("port_json")
    if pj:
        try:
            loaded = json.loads(pj)
            if isinstance(loaded, list):
                return [str(p) for p in loaded if p]
        except json.JSONDecodeError:
            pass
    return []


def _port_path_matches(actual: str, pattern: str, op: str) -> bool:
    if op == "=":
        return actual == pattern
    if op == "^=":
        return actual.startswith(pattern)
    if op == "~":
        import fnmatch

        return fnmatch.fnmatchcase(actual, pattern)
    return True


def apply_expand_ports(
    rows: List[Dict[str, Any]],
    *,
    port_path_filter: Optional[str] = None,
    port_path_filter_op: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """B-mode: one row per (instance, port) with ``port_path`` = ``full_path.port``."""
    out: List[Dict[str, Any]] = []
    for r in rows:
        fp = r.get("full_path", "")
        ports = _port_names(r)
        if not ports:
            row = dict(r)
            row["port_path"] = fp
            row["port_name"] = ""
            if port_path_filter and not _port_path_matches(
                row["port_path"], port_path_filter, port_path_filter_op or "="
            ):
                continue
            out.append(row)
            continue
        for pname in ports:
            port_path = f"{fp}.{pname}" if fp else pname
            if port_path_filter and not _port_path_matches(
                port_path, port_path_filter, port_path_filter_op or "="
            ):
                continue
            row = dict(r)
            row["port_path"] = port_path
            row["port_name"] = pname
            out.append(row)
    return out


def apply_post_filters(
    rows: list,
    *,
    lastnode: bool = False,
    expand_ports: bool = False,
    port_path_filter: Optional[str] = None,
    port_path_filter_op: Optional[str] = None,
) -> list:
    if lastnode:
        rows = apply_lastnode(rows)
    if expand_ports:
        rows = apply_expand_ports(
            rows,
            port_path_filter=port_path_filter,
            port_path_filter_op=port_path_filter_op,
        )
    return rows