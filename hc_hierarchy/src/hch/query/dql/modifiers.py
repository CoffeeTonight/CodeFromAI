"""DQL query modifiers stripped before Lark parse."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


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


def apply_expand_ports(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """B-mode: one row per (instance, port) with ``port_path`` = ``full_path.port``."""
    out: List[Dict[str, Any]] = []
    for r in rows:
        fp = r.get("full_path", "")
        ports = _port_names(r)
        if not ports:
            row = dict(r)
            row["port_path"] = fp
            row["port_name"] = ""
            out.append(row)
            continue
        for pname in ports:
            row = dict(r)
            row["port_path"] = f"{fp}.{pname}" if fp else pname
            row["port_name"] = pname
            out.append(row)
    return out


def apply_post_filters(
    rows: list,
    *,
    lastnode: bool = False,
    expand_ports: bool = False,
) -> list:
    if lastnode:
        rows = apply_lastnode(rows)
    if expand_ports:
        rows = apply_expand_ports(rows)
    return rows