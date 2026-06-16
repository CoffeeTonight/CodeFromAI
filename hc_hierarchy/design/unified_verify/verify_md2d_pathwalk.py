#!/usr/bin/env python3
"""Assert path-walk on multi-dim instance arrays: a.b.c[0][1].d.e.f[1].g[0][2]."""

from __future__ import annotations

from pathlib import Path

from verify_report import (
    CheckResult,
    emit_report,
    parse_conn_tsv,
    parse_cone_tsv,
    parse_io_tsv,
)

DEEP_A = "hc_verify_top.u_md2d.a.b.c[0][1].d.e.f[1].g[0][2]"
DEEP_B = "hc_verify_top.u_md2d.a2.b.c[1][0].d.e.f[0].g[1][1]"


def _scopes_match(scopes: list[str], needles: tuple[str, ...], *, min_hits: int) -> bool:
    hits = sum(1 for n in needles if any(n in s for s in scopes))
    return hits >= min_hits


def _conn_checks(root: Path) -> list[CheckResult]:
    conn_path = root / "out_pw_md2d_conn.tsv"
    wire_checks = (
        "pw_md2d_wire_leaf_out",
        "pw_md2d_wire_f_out",
        "pw_md2d_wire_c_out",
        "pw_md2d_wire_top_sink",
        "pw_md2d_wire_probe_src",
    )
    check_ids = (
        "pw_md2d_hier",
        "pw_md2d_clk",
        "pw_md2d_branch_link",
        "pw_md2d_src_to_a",
        "pw_md2d_b_to_sink",
        *wire_checks,
    )
    if not conn_path.is_file():
        return [
            CheckResult(
                name=check_id,
                category="conn",
                passed=False,
                summary="missing TSV",
                issues=[f"missing {conn_path.name}"],
                tsv=conn_path.name,
            )
            for check_id in check_ids
        ]
    data = parse_conn_tsv(conn_path)
    results: list[CheckResult] = []
    for check_id in check_ids:
        row = data["checks"].get(check_id)
        if row is None:
            results.append(
                CheckResult(
                    name=check_id,
                    category="conn",
                    passed=False,
                    summary="check missing in TSV",
                    issues=[f"{check_id} not found"],
                    tsv=conn_path.name,
                )
            )
            continue
        ok = row["connected"] == "True"
        tag = "wire" if check_id in wire_checks else "port"
        results.append(
            CheckResult(
                name=check_id,
                category=f"conn/{tag}",
                passed=ok,
                summary=f"connected={row['connected']} mode={row['mode']}",
                issues=[] if ok else [f"connected={row['connected']!r}"],
                nodes=[row["endpoint_a_prov"], row["endpoint_b_prov"]],
                tsv=conn_path.name,
            )
        )
    return results


def _fanin_check(root: Path) -> CheckResult:
    fanin_path = root / "out_pw_md2d_fanin_clk.tsv"
    if not fanin_path.is_file():
        return CheckResult(
            name="fanin_clk",
            category="cone",
            passed=False,
            summary="missing TSV",
            issues=[f"missing {fanin_path.name}"],
            tsv=fanin_path.name,
        )
    data = parse_cone_tsv(fanin_path)
    ok = True
    issues: list[str] = []
    if data.get("origin") != f"{DEEP_A}.clk":
        ok = False
        issues.append(f"origin={data.get('origin')}")
    if data["boundary_count"] < 1:
        ok = False
        issues.append(f"boundary_count={data['boundary_count']}")
    needles = ("c[0][1]", "f[1]", "g[0][2]")
    if not _scopes_match(data.get("scopes", []), needles, min_hits=2):
        ok = False
        issues.append(f"scopes need 2 of {needles}; got {data.get('scopes', [])}")
    return CheckResult(
        name="fanin_clk",
        category="cone",
        passed=ok,
        summary=(
            f"boundaries={data['boundary_count']} origin={data.get('origin')}"
        ),
        issues=issues,
        nodes=[data["origin_node"], *data.get("boundaries", [])],
        tsv=fanin_path.name,
    )


def _io_check(root: Path) -> CheckResult:
    io_path = root / "out_pw_md2d_io_driver.tsv"
    if not io_path.is_file():
        return CheckResult(
            name="io_driver",
            category="io",
            passed=False,
            summary="missing TSV",
            issues=[f"missing {io_path.name}"],
            tsv=io_path.name,
        )
    data = parse_io_tsv(io_path)
    ok = True
    issues: list[str] = []
    if data.get("instance") != DEEP_A:
        ok = False
        issues.append(f"instance={data.get('instance')}")
    if data["boundary_count"] < 1:
        ok = False
        issues.append(f"boundary_count={data['boundary_count']}")
    if not _scopes_match(data.get("scopes", []), ("g[0][2]", "c[0][1]"), min_hits=1):
        ok = False
        issues.append(f"scopes={data.get('scopes', [])}")
    return CheckResult(
        name="io_driver",
        category="io",
        passed=ok,
        summary=f"boundaries={data['boundary_count']} instance={DEEP_A}",
        issues=issues,
        nodes=[data["instance_node"], *data.get("boundaries", [])],
        tsv=io_path.name,
    )


def main() -> int:
    root = Path(__file__).resolve().parent
    results = _conn_checks(root) + [_fanin_check(root), _io_check(root)]
    return emit_report(
        f"unified_verify md2d path-walk (A={DEEP_A}, B={DEEP_B})",
        results,
        report_path=root / "verify_md2d_pathwalk.report.txt",
    )


if __name__ == "__main__":
    raise SystemExit(main())