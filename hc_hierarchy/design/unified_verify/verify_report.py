"""Shared report formatting for unified_verify check scripts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence


@dataclass
class NodeProvenance:
    """RTL + filelist provenance for one hierarchy scope or endpoint."""

    scope: str
    role: str = ""
    module: str = ""
    rtl: str = ""
    via_filelist: str = ""
    filelist_chain: str = ""

    def format_line(self, *, indent: str = "    ") -> str:
        parts = [self.scope]
        if self.role:
            parts.append(f"role={self.role}")
        if self.module:
            parts.append(f"module={self.module}")
        if self.rtl:
            parts.append(f"rtl={self.rtl}")
        if self.via_filelist:
            parts.append(f"via_filelist={self.via_filelist}")
        if self.filelist_chain:
            parts.append(f"filelist_chain={self.filelist_chain}")
        return f"{indent}{'  '.join(parts)}"


@dataclass
class CheckResult:
    """One logical verification check with optional node provenance."""

    name: str
    category: str
    passed: bool
    summary: str = ""
    issues: list[str] = field(default_factory=list)
    nodes: list[NodeProvenance] = field(default_factory=list)
    tsv: str = ""

    @property
    def status(self) -> str:
        return "PASS" if self.passed else "FAIL"


_PROV_FIELDS = ("rtl", "via_filelist", "filelist_chain")


def _split_tsv_line(line: str) -> list[str]:
    return line.split("\t")


def _prov_from_row(
    scope: str,
    row: Sequence[str],
    col_map: dict[str, int],
    *,
    role: str = "",
    module: str = "",
) -> NodeProvenance:
    def _get(key: str) -> str:
        idx = col_map.get(key)
        if idx is None or idx >= len(row):
            return ""
        return row[idx]

    mod = _get("module") or module
    return NodeProvenance(
        scope=scope,
        role=role,
        module=mod,
        rtl=_get("rtl"),
        via_filelist=_get("via_filelist"),
        filelist_chain=_get("filelist_chain"),
    )


def _header_col_map(header: list[str]) -> dict[str, int]:
    return {name: i for i, name in enumerate(header)}


def parse_conn_tsv(path: Path) -> dict:
    """Parse connect TSV; returns meta + checks dict keyed by check_id."""
    meta: dict[str, str] = {}
    checks: dict[str, dict] = {}
    header: list[str] = []
    col_map: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        if line.startswith("#"):
            parts = _split_tsv_line(line[1:])
            if len(parts) >= 2:
                meta[parts[0].strip()] = parts[1].strip()
            continue
        parts = _split_tsv_line(line)
        if not header:
            header = parts
            col_map = _header_col_map(header)
            continue
        if not parts or parts[0] == "check_id":
            continue
        check_id = parts[0]
        connected = parts[col_map.get("connected", 3)] if len(parts) > 3 else ""
        checks[check_id] = {
            "connected": connected,
            "endpoint_a": parts[col_map.get("endpoint_a", 1)] if len(parts) > 1 else "",
            "endpoint_b": parts[col_map.get("endpoint_b", 2)] if len(parts) > 2 else "",
            "mode": parts[col_map.get("mode", 4)] if len(parts) > 4 else "",
            "note": parts[col_map.get("note", 5)] if len(parts) > 5 else "",
            "endpoint_a_prov": _prov_from_row(
                parts[col_map.get("endpoint_a", 1)] if len(parts) > 1 else "",
                parts,
                {
                    "rtl": col_map.get("a_rtl"),
                    "via_filelist": col_map.get("a_via_filelist"),
                    "filelist_chain": col_map.get("a_filelist_chain"),
                },
                role="endpoint_a",
            ),
            "endpoint_b_prov": _prov_from_row(
                parts[col_map.get("endpoint_b", 2)] if len(parts) > 2 else "",
                parts,
                {
                    "rtl": col_map.get("b_rtl"),
                    "via_filelist": col_map.get("b_via_filelist"),
                    "filelist_chain": col_map.get("b_filelist_chain"),
                },
                role="endpoint_b",
            ),
        }
    return {"meta": meta, "checks": checks, "header": header}


def parse_cone_tsv(path: Path) -> dict:
    """Parse cone TSV with boundary provenance and origin meta."""
    meta: dict[str, str] = {}
    rows: list[list[str]] = []
    header: list[str] = []
    col_map: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        if line.startswith("#"):
            parts = _split_tsv_line(line[1:])
            if len(parts) >= 2:
                meta[parts[0].strip()] = parts[1].strip()
            continue
        parts = _split_tsv_line(line)
        if not header:
            header = parts
            col_map = _header_col_map(header)
            continue
        rows.append(parts)
    data_rows = rows
    boundaries: list[NodeProvenance] = []
    kinds: list[str] = []
    scopes: list[str] = []
    for row in data_rows:
        if not row:
            continue
        kind = row[0]
        kinds.append(kind)
        scope = row[col_map.get("scope", 1)] if len(row) > 1 else ""
        scopes.append(scope)
        boundaries.append(
            _prov_from_row(
                scope,
                row,
                col_map,
                role=kind,
                module=row[col_map.get("module", 3)] if len(row) > 3 else "",
            )
        )
    origin_scope = meta.get("origin", "")
    origin = NodeProvenance(
        scope=origin_scope,
        role="origin",
        rtl=meta.get("origin_rtl", ""),
        via_filelist=meta.get("origin_via_filelist", ""),
        filelist_chain=meta.get("origin_filelist_chain", ""),
    )
    return {
        **meta,
        "boundary_count": len(data_rows),
        "kinds": kinds,
        "scopes": scopes,
        "boundaries": boundaries,
        "origin_node": origin,
    }


def parse_io_tsv(path: Path) -> dict:
    """Parse inst-trace (io) TSV with boundary provenance and instance meta."""
    meta: dict[str, str] = {}
    rows: list[list[str]] = []
    header: list[str] = []
    col_map: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        if line.startswith("#"):
            parts = _split_tsv_line(line[1:])
            if len(parts) >= 2:
                meta[parts[0].strip()] = parts[1].strip()
            continue
        parts = _split_tsv_line(line)
        if not header:
            header = parts
            col_map = _header_col_map(header)
            continue
        rows.append(parts)
    boundaries_raw = rows
    boundaries: list[NodeProvenance] = []
    origins: set[str] = set()
    scopes: list[str] = []
    kinds: list[str] = []
    by_port: dict[str, int] = {}
    for row in boundaries_raw:
        if not row:
            continue
        port = row[0]
        origins.add(port)
        by_port[port] = by_port.get(port, 0) + 1
        kind = row[col_map.get("boundary_kind", 2)] if len(row) > 2 else ""
        kinds.append(kind)
        scope = row[col_map.get("scope", 3)] if len(row) > 3 else ""
        scopes.append(scope)
        boundaries.append(
            _prov_from_row(
                scope,
                row,
                col_map,
                role=f"{port}/{kind}",
                module=row[col_map.get("module", 5)] if len(row) > 5 else "",
            )
        )
    instance_scope = meta.get("instance", "")
    instance = NodeProvenance(
        scope=instance_scope,
        role="instance",
        module=meta.get("module", ""),
        rtl=meta.get("instance_rtl", ""),
        via_filelist=meta.get("instance_via_filelist", ""),
        filelist_chain=meta.get("instance_filelist_chain", ""),
    )
    return {
        **meta,
        "boundary_count": len(boundaries_raw),
        "origin_ports": origins,
        "scopes": scopes,
        "kinds": kinds,
        "by_port": by_port,
        "boundaries": boundaries,
        "instance_node": instance,
    }


def _col_widths(rows: Sequence[Sequence[str]]) -> list[int]:
    if not rows:
        return []
    ncols = max(len(r) for r in rows)
    widths = [0] * ncols
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    return widths


def _format_table(rows: Sequence[Sequence[str]]) -> str:
    if not rows:
        return ""
    widths = _col_widths(rows)
    lines: list[str] = []
    for i, row in enumerate(rows):
        padded = [
            (row[j] if j < len(row) else "").ljust(widths[j])
            for j in range(len(widths))
        ]
        lines.append("  ".join(padded))
        if i == 0:
            lines.append("  ".join("-" * w for w in widths))
    return "\n".join(lines)


def format_summary_table(results: Sequence[CheckResult]) -> str:
    """Compact summary table with pass rate."""
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    pct = (100.0 * passed / total) if total else 0.0
    rows = [
        ("metric", "value"),
        ("total", str(total)),
        ("pass", str(passed)),
        ("fail", str(failed)),
        ("pass_rate", f"{pct:.1f}%"),
    ]
    detail_rows = [("check", "category", "status", "summary")]
    for r in results:
        detail_rows.append((r.name, r.category, r.status, r.summary or "-"))
    return (
        "SUMMARY\n"
        + _format_table(rows)
        + "\n\n"
        + _format_table(detail_rows)
    )


def format_failed_list(results: Sequence[CheckResult]) -> str:
    """List only failed checks with issue messages."""
    failed = [r for r in results if not r.passed]
    if not failed:
        return "FAILED\n(none)\n"
    lines = ["FAILED"]
    for r in failed:
        lines.append(f"  [{r.category}] {r.name}: {'; '.join(r.issues) or r.summary}")
    return "\n".join(lines) + "\n"


def _dedupe_nodes(nodes: Iterable[NodeProvenance]) -> list[NodeProvenance]:
    seen: set[tuple[str, str]] = set()
    out: list[NodeProvenance] = []
    for n in nodes:
        key = (n.scope, n.role)
        if key in seen:
            continue
        seen.add(key)
        out.append(n)
    return out


def format_detail_section(results: Sequence[CheckResult]) -> str:
    """Per-check detail with all verification nodes and rtl/filelist."""
    lines = ["DETAIL"]
    for r in results:
        lines.append(f"\n[{r.status}] {r.name} ({r.category})")
        if r.tsv:
            lines.append(f"  tsv: {r.tsv}")
        if r.summary:
            lines.append(f"  summary: {r.summary}")
        if r.issues:
            lines.append(f"  issues: {'; '.join(r.issues)}")
        nodes = _dedupe_nodes(r.nodes)
        if nodes:
            lines.append("  nodes:")
            for n in nodes:
                lines.append(n.format_line(indent="    "))
        else:
            lines.append("  nodes: (none)")
    return "\n".join(lines) + "\n"


def format_report(title: str, results: Sequence[CheckResult]) -> str:
    """Full report: summary table, failed list, then detail."""
    parts = [
        title,
        "=" * len(title),
        "",
        format_summary_table(results),
        "",
        format_failed_list(results),
        "",
        format_detail_section(results),
    ]
    return "\n".join(parts)


def write_report(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def emit_report(
    title: str,
    results: Sequence[CheckResult],
    *,
    report_path: Path | None = None,
) -> int:
    """Print report to stdout and optionally write to disk; return exit code."""
    text = format_report(title, results)
    print(text)
    if report_path is not None:
        write_report(report_path, text)
    return 0 if all(r.passed for r in results) else 1