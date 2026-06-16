"""Hierarchy node provenance for stderr / error reports."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import IO, List, Mapping, Optional, Sequence, TextIO

from scan_inst.models import ConnectEndpoint, ConnectHop, FlatRow, PathChainLink

_PREFIX = "[scan-inst hierarchy]"
_PATH_WALK_PREFIX = "[scan-inst path-walk]"


def provenance_fields(
    scope: str,
    rows_by_path: Mapping[str, FlatRow],
) -> dict[str, str]:
    """Machine-readable rtl + filelist fields for one hierarchy *scope*."""
    row = rows_by_path.get(scope) if scope else None
    if row is None:
        return {
            "module": "",
            "rtl": "",
            "via_filelist": "",
            "filelist_chain": "",
        }
    return {
        "module": row.module,
        "rtl": row.file or "",
        "via_filelist": row.via_filelist or "",
        "filelist_chain": row.filelist_chain or "",
    }


def endpoint_provenance_fields(
    ep: ConnectEndpoint,
    rows_by_path: Mapping[str, FlatRow],
) -> dict[str, str]:
    """Provenance for a connect/io endpoint (inst path + optional port)."""
    base = provenance_fields(ep.inst_path, rows_by_path)
    if ep.port_name and not base["rtl"]:
        base["note"] = ep.spec
    elif ep.port_name:
        base["port"] = ep.port_name
    if ep.module and not base["module"]:
        base["module"] = ep.module
    return base


def format_row_provenance(row: FlatRow, *, compact: bool = False) -> str:
    """RTL file + filelist chain for one elaborated instance row."""
    parts = [f"module={row.module}"]
    if row.file:
        parts.append(f"rtl={row.file}" if not compact else f"rtl={Path(row.file).name}")
    if row.via_filelist:
        via = row.via_filelist if not compact else Path(row.via_filelist).name
        parts.append(f"via_filelist={via}")
    if row.filelist_chain:
        parts.append(f"filelist_chain={row.filelist_chain}")
    if row.stop_reason:
        parts.append(f"stop={row.stop_reason}")
    return "  ".join(parts)


def format_hierarchy_row_line(row: FlatRow) -> str:
    return f"{row.full_path}  {format_row_provenance(row)}"


def format_hierarchy_rows_report(
    rows: Sequence[FlatRow],
    *,
    limit: Optional[int] = None,
    title: str = "Hierarchy instances (rtl + filelist)",
) -> List[str]:
    lines = [title]
    shown = list(rows) if limit is None else list(rows[:limit])
    for row in shown:
        lines.append(f"  {format_hierarchy_row_line(row)}")
    if limit is not None and len(rows) > limit:
        lines.append(f"  ... {len(rows) - limit} more (see output TSV)")
    return lines


def emit_hierarchy_rows_log(
    rows: Sequence[FlatRow],
    *,
    stream: TextIO,
    limit: Optional[int] = 200,
    title: Optional[str] = None,
) -> None:
    if not rows:
        return
    head = title or f"{len(rows)} instance(s)"
    print(f"{_PREFIX} {head}", file=stream, flush=True)
    shown = list(rows) if limit is None or len(rows) <= limit else list(rows[:limit])
    for row in shown:
        print(f"{_PREFIX}   {format_hierarchy_row_line(row)}", file=stream, flush=True)
    if limit is not None and len(rows) > limit:
        print(
            f"{_PREFIX}   ... {len(rows) - limit} more (see output TSV)",
            file=stream,
            flush=True,
        )


def rows_lookup(rows: Sequence[FlatRow]) -> dict[str, FlatRow]:
    return {r.full_path: r for r in rows}


def format_endpoint_provenance_line(
    label: str,
    ep: ConnectEndpoint,
    rows_by_path: Mapping[str, FlatRow],
) -> str:
    """One endpoint with rtl + filelist when elaboration row exists."""
    row = rows_by_path.get(ep.inst_path) if ep.inst_path else None
    port_note = f"  port={ep.port_name}" if ep.port_name else ""
    if row is not None:
        return f"{label}: {format_hierarchy_row_line(row)}{port_note}"
    parts = [f"{label}: {ep.spec}"]
    if ep.module:
        parts.append(f"module={ep.module}")
    if ep.inst_path:
        parts.append(f"inst={ep.inst_path}")
    parts.append("(no elaboration row)")
    return "  ".join(parts)


def format_path_provenance_line(
    label: str,
    path: str,
    rows_by_path: Mapping[str, FlatRow],
) -> str:
    row = rows_by_path.get(path) if path else None
    if row is not None:
        return f"{label}: {format_hierarchy_row_line(row)}"
    return f"{label}: {path}  (no elaboration row)"


def emit_path_provenance_log(
    path: str,
    rows_by_path: Mapping[str, FlatRow],
    *,
    stream: TextIO,
    label: str = "origin",
    prefix: str = _PREFIX,
) -> None:
    if not path:
        return
    print(
        f"{prefix} {format_path_provenance_line(label, path, rows_by_path)}",
        file=stream,
        flush=True,
    )


def _lca(path_a: str, path_b: str) -> str:
    parts_a = path_a.split(".")
    parts_b = path_b.split(".")
    common: List[str] = []
    for a, b in zip(parts_a, parts_b):
        if a != b:
            break
        common.append(a)
    return ".".join(common)


def hierarchy_spine_between(path_a: str, path_b: str) -> List[str]:
    """Ordered instance paths from LCA down each endpoint branch."""
    if not path_a and not path_b:
        return []
    if not path_a:
        path_a = path_b
    if not path_b:
        path_b = path_a
    lca = _lca(path_a, path_b)
    lca_depth = len(lca.split(".")) if lca else 0
    nodes: List[str] = []
    seen: set[str] = set()

    def _append(path: str) -> None:
        if path and path not in seen:
            seen.add(path)
            nodes.append(path)

    for end in (path_a, path_b):
        parts = end.split(".")
        for depth in range(max(lca_depth, 1), len(parts) + 1):
            _append(".".join(parts[:depth]))
    return nodes


def scopes_from_hop_detail(detail: str) -> List[str]:
    """Extract hierarchy scopes from connect hop detail (scope:net labels)."""
    if not detail or detail == "structural COI path":
        return []
    head = detail.split(" (", 1)[0]
    scopes: List[str] = []
    seen: set[str] = set()
    for part in head.split(" -> "):
        part = part.strip()
        if not part:
            continue
        scope = part.rsplit(":", 1)[0] if ":" in part else part
        if scope not in seen:
            seen.add(scope)
            scopes.append(scope)
    return scopes


def collect_hop_scopes(hops: Sequence[ConnectHop]) -> List[str]:
    """Ordered unique scopes referenced by connect hop details."""
    scopes: List[str] = []
    seen: set[str] = set()
    for hop in hops:
        for scope in scopes_from_hop_detail(hop.detail):
            if scope not in seen:
                seen.add(scope)
                scopes.append(scope)
    return scopes


def format_scope_provenance_line(
    scope: str,
    rows_by_path: Mapping[str, FlatRow],
) -> str:
    row = rows_by_path.get(scope)
    if row is not None:
        return format_hierarchy_row_line(row)
    return f"{scope}  (no elaboration row)"


def format_scopes_provenance_lines(
    scopes: Sequence[str],
    rows_by_path: Mapping[str, FlatRow],
    *,
    indent: str = "  ",
) -> List[str]:
    return [f"{indent}{format_scope_provenance_line(scope, rows_by_path)}" for scope in scopes]


def emit_scopes_provenance_log(
    scopes: Sequence[str],
    rows_by_path: Mapping[str, FlatRow],
    *,
    stream: TextIO,
    prefix: str,
    title: str,
    indent: str = "  ",
) -> None:
    if not scopes:
        return
    if title:
        print(f"{prefix}   {title}", file=stream, flush=True)
    for line in format_scopes_provenance_lines(scopes, rows_by_path, indent=indent):
        print(f"{prefix}   {line}", file=stream, flush=True)


def path_spine_prefixes(path: str) -> List[str]:
    """Ordered instance paths from root down to *path* (inclusive)."""
    parts = path.split(".")
    return [".".join(parts[: depth + 1]) for depth in range(len(parts))]


def format_path_walk_node_line(
    path: str,
    row: FlatRow,
    *,
    action: str = "ok",
) -> str:
    return f"{action} {path}  {format_row_provenance(row)}"


def format_path_walk_miss_line(
    parent_path: str,
    parent_row: FlatRow,
    inst_leaf: str,
    *,
    reason: str,
) -> str:
    return (
        f"miss inst={inst_leaf} under {parent_path} ({reason})  "
        f"parent {format_row_provenance(parent_row)}"
    )


def format_path_walk_spine_lines(
    path: str,
    rows_by_path: Mapping[str, FlatRow],
    *,
    indent: str = "  ",
) -> List[str]:
    lines: List[str] = []
    for prefix in path_spine_prefixes(path):
        row = rows_by_path.get(prefix)
        if row is None:
            lines.append(f"{indent}{prefix}  (no elaboration row)")
            break
        lines.append(f"{indent}{format_path_walk_node_line(prefix, row)}")
    return lines


def path_walk_trace_show_message(message: str) -> bool:
    """
    Whether a path-walk trace line should be emitted.

    Search steps (tier0/tier1 scans, candidate tries, expands) are suppressed;
    resolved nodes and pw-db hits are kept. Miss lines are kept on failure.
    """
    msg = message.strip()
    if not msg:
        return False
    if msg.startswith("walk target="):
        return False
    if msg.startswith("pw-db v"):
        return False
    if msg.startswith("pw-db "):
        if " load failed " in msg:
            return True
        return " edge hit " in msg or msg.startswith("pw-db   hit ")
    return True


def open_path_walk_trace_log(log_path: Path) -> TextIO:
    """Append path-walk trace section to the run log file."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fh = log_path.open("a", encoding="utf-8")
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fh.write(f"\n# path-walk trace {stamp}\n")
    fh.flush()
    return fh


def emit_path_walk_log(
    message: str,
    *,
    stream: TextIO,
    prefix: str = _PATH_WALK_PREFIX,
) -> None:
    if not message:
        return
    print(f"{prefix} {message}", file=stream, flush=True)


def emit_path_walk_node_log(
    path: str,
    row: FlatRow,
    *,
    stream: TextIO,
    action: str = "ok",
    prefix: str = _PATH_WALK_PREFIX,
) -> None:
    emit_path_walk_log(
        format_path_walk_node_line(path, row, action=action),
        stream=stream,
        prefix=prefix,
    )


def emit_path_walk_miss_log(
    parent_path: str,
    parent_row: FlatRow,
    inst_leaf: str,
    *,
    stream: TextIO,
    reason: str,
    prefix: str = _PATH_WALK_PREFIX,
) -> None:
    emit_path_walk_log(
        format_path_walk_miss_line(parent_path, parent_row, inst_leaf, reason=reason),
        stream=stream,
        prefix=prefix,
    )
    for line in format_path_walk_spine_lines(parent_path, {parent_path: parent_row}):
        print(f"{prefix} {line}", file=stream, flush=True)


def emit_path_walk_spine_log(
    path: str,
    rows_by_path: Mapping[str, FlatRow],
    *,
    stream: TextIO,
    title: str = "spine",
    prefix: str = _PATH_WALK_PREFIX,
) -> None:
    if not path:
        return
    emit_path_walk_log(f"{title} -> {path}", stream=stream, prefix=prefix)
    for line in format_path_walk_spine_lines(path, rows_by_path):
        print(f"{prefix} {line}", file=stream, flush=True)


def format_path_link_provenance(link: PathChainLink) -> str:
    parts: List[str] = []
    if link.rtl_file:
        parts.append(f"rtl={link.rtl_file}")
    if link.inst_decl_file and link.inst_decl_file != link.rtl_file:
        parts.append(f"decl_in={link.inst_decl_file}")
    if link.via_filelist:
        parts.append(f"via_filelist={link.via_filelist}")
    if link.filelist_chain:
        parts.append(f"filelist_chain={link.filelist_chain}")
    if link.inst_decl_via_filelist:
        parts.append(f"decl_via_filelist={link.inst_decl_via_filelist}")
    if link.inst_decl_filelist_chain:
        parts.append(f"decl_filelist_chain={link.inst_decl_filelist_chain}")
    return "  ".join(parts)