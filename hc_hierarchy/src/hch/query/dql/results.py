"""Format DQL query result rows as text or TSV."""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional


def _ports_cell(row: Dict[str, Any]) -> str:
    pj = row.get("port_json")
    if pj:
        try:
            loaded = json.loads(pj)
            if isinstance(loaded, list):
                return ",".join(str(p) for p in loaded)
        except json.JSONDecodeError:
            pass
    ports = row.get("ports")
    if isinstance(ports, list):
        return ",".join(str(p) for p in ports)
    return ""


def _inst_name(row: Dict[str, Any]) -> str:
    if row.get("inst_leaf_name"):
        return str(row["inst_leaf_name"])
    if row.get("inst"):
        return str(row["inst"])
    fp = row.get("full_path") or ""
    return fp.split(".")[-1] if fp else ""


def normalize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    out = {
        "full_path": row.get("full_path", ""),
        "inst": _inst_name(row),
        "module": row.get("module_name") or row.get("module", ""),
        "file": row.get("filepath") or row.get("file", ""),
        "depth": row.get("depth", 0),
        "parent": row.get("parent_path") or row.get("parent") or "",
        "ports": _ports_cell(row),
    }
    if "port_path" in row:
        out["port_path"] = row.get("port_path", "")
        out["port_name"] = row.get("port_name", "")
    return out


def format_rows_text(
    rows: Iterable[Dict[str, Any]],
    *,
    query: str = "",
    include_header: bool = True,
) -> str:
    lines: List[str] = []
    if query:
        lines.append(f"# {query}")
    expanded = any("port_path" in (raw if isinstance(raw, dict) else {}) for raw in rows)
    if include_header:
        if expanded:
            lines.append(
                "port_path\tfull_path\tinst\tmodule\tfile\tdepth\tparent\tport_name"
            )
        else:
            lines.append("full_path\tinst\tmodule\tfile\tdepth\tparent\tports")
    for raw in rows:
        r = normalize_row(raw)
        if expanded:
            lines.append(
                f"{r.get('port_path','')}\t{r['full_path']}\t{r['inst']}\t{r['module']}"
                f"\t{r['file']}\t{r['depth']}\t{r.get('parent','')}\t{r.get('port_name','')}"
            )
        else:
            lines.append(
                f"{r['full_path']}\t{r['inst']}\t{r['module']}\t{r['file']}"
                f"\t{r['depth']}\t{r.get('parent','')}\t{r['ports']}"
            )
    return "\n".join(lines) + ("\n" if lines else "")


def format_rows_plain(
    rows: Iterable[Dict[str, Any]],
    *,
    query: str = "",
) -> str:
    """Human-readable multi-line text (one block per hit)."""
    blocks: List[str] = []
    if query:
        blocks.append(f"# Query: {query}\n")
    for i, raw in enumerate(rows, 1):
        r = normalize_row(raw)
        extra = ""
        if r.get("port_path"):
            extra = f"    port_path: {r['port_path']}\n    port:      {r.get('port_name','')}\n"
        blocks.append(
            f"[{i}] {r['full_path']}\n"
            f"    inst:   {r['inst']}\n"
            f"    module: {r['module']}\n"
            f"    file:   {r['file']}\n"
            f"    depth:  {r['depth']}\n"
            f"    parent: {r.get('parent') or '-'}\n"
            f"{extra}"
            f"    ports:  {r['ports'] or '-'}\n"
        )
    return "\n".join(blocks)