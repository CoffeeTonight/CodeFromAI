#!/usr/bin/env python3
"""Assert multi-boundary fanin/fanout + generate paths (full-index and path-walk)."""

from __future__ import annotations

from pathlib import Path

from verify_report import (
    CheckResult,
    emit_report,
    parse_conn_tsv,
    parse_cone_tsv,
    parse_io_tsv,
)


def _scopes_match(scopes: list[str], needles: tuple[str, ...], *, min_hits: int) -> bool:
    hits = sum(
        1
        for needle in needles
        if any(needle in scope for scope in scopes)
    )
    return hits >= min_hits


def _cone_io_checks(root: Path) -> list[CheckResult]:
    specs: list[tuple[str, Path, str, dict]] = [
        (
            "fanout_top_clk",
            root / "out_multifan_fanout_top_clk.tsv",
            "cone",
            {
                "boundary_count_min": 4,
                "port_count_min": 3,
                "generate_scopes": ("gen_blk.gen_loop", "gen_on"),
                "generate_min": 2,
            },
        ),
        (
            "fanin_top_clk",
            root / "out_multifan_fanin_top_clk.tsv",
            "cone",
            {"boundary_count_min": 6, "port_count_min": 5},
        ),
        (
            "fanin_gen_soc_clk",
            root / "out_multifan_fanin_gen_soc_clk.tsv",
            "cone",
            {
                "boundary_count_min": 4,
                "port_count_min": 4,
                "generate_scopes": ("gen_blk.gen_loop[0].u_cell", "gen_blk.gen_loop[1].u_cell"),
                "generate_min": 2,
            },
        ),
        (
            "fanout_cell_done",
            root / "out_multifan_fanout_cell_done.tsv",
            "cone",
            {
                "boundary_count_min": 4,
                "port_count_min": 3,
                "generate_scopes": ("gen_blk.gen_loop", "gen_on"),
                "generate_min": 2,
            },
        ),
        (
            "fanin_cell_done",
            root / "out_multifan_fanin_cell_done.tsv",
            "cone",
            {"boundary_count_min": 3, "port_count_min": 2},
        ),
        (
            "io_driver_gen_soc",
            root / "out_multifan_io_gen_soc_driver.tsv",
            "io",
            {
                "boundary_count_min": 8,
                "ports_min": 2,
                "generate_scopes": ("gen_blk.gen_loop[0].u_cell", "gen_blk.gen_loop[1].u_cell"),
                "generate_min": 2,
            },
        ),
        (
            "io_sinker_gen_soc",
            root / "out_multifan_io_gen_soc_sinker.tsv",
            "io",
            {
                "boundary_count_min": 3,
                "ports_min": 1,
                "generate_scopes": ("gen_blk.gen_loop[0].u_cell", "gen_blk.gen_loop[1].u_cell"),
                "generate_min": 2,
            },
        ),
        (
            "pw_fanin_gen_soc_clk",
            root / "out_pw_multifan_fanin_gen_soc_clk.tsv",
            "cone",
            {
                "boundary_count_min": 4,
                "port_count_min": 4,
                "generate_scopes": ("gen_blk.gen_loop[0].u_cell", "gen_blk.gen_loop[1].u_cell"),
                "generate_min": 2,
            },
        ),
        (
            "pw_fanin_gen_cell_clk",
            root / "out_pw_multifan_fanin_gen_cell_clk.tsv",
            "cone",
            {
                "boundary_count_min": 2,
                "port_count_min": 2,
                "generate_scopes": ("gen_blk.gen_loop[0].u_cell",),
                "generate_min": 1,
            },
        ),
        (
            "pw_fanout_gen_if_done",
            root / "out_pw_multifan_fanout_gen_if_done.tsv",
            "cone",
            {
                "boundary_count_min": 1,
                "port_count_min": 1,
                "generate_scopes": ("gen_on.u_on",),
                "generate_min": 1,
            },
        ),
        (
            "pw_io_driver_gen_soc",
            root / "out_pw_multifan_io_gen_soc_driver.tsv",
            "io",
            {
                "boundary_count_min": 8,
                "ports_min": 2,
                "generate_scopes": ("gen_blk.gen_loop[0].u_cell", "gen_blk.gen_loop[1].u_cell"),
                "generate_min": 2,
            },
        ),
    ]

    results: list[CheckResult] = []
    for name, path, kind, expect in specs:
        if not path.is_file():
            results.append(
                CheckResult(
                    name=name,
                    category=kind,
                    passed=False,
                    summary="missing TSV",
                    issues=[f"missing {path.name}"],
                    tsv=path.name,
                )
            )
            continue
        data = parse_io_tsv(path) if kind == "io" else parse_cone_tsv(path)
        ok = True
        issues: list[str] = []

        bmin = expect.get("boundary_count_min", 2)
        if data["boundary_count"] < bmin:
            ok = False
            issues.append(f"boundary_count={data['boundary_count']} < {bmin}")

        gen_needles = expect.get("generate_scopes")
        if gen_needles:
            gmin = expect.get("generate_min", 1)
            if not _scopes_match(data.get("scopes", []), gen_needles, min_hits=gmin):
                ok = False
                issues.append(
                    f"generate scopes need {gmin} of {gen_needles}; "
                    f"got {data.get('scopes', [])[:6]}"
                )

        if kind == "cone":
            pmin = expect.get("port_count_min", 2)
            if int(data.get("port_count", "0")) < pmin:
                ok = False
                issues.append(f"port_count={data.get('port_count')} < {pmin}")
            summary = (
                f"boundaries={data['boundary_count']} "
                f"port_count={data.get('port_count')} "
                f"direction={data.get('direction')}"
            )
            nodes = [data["origin_node"], *data.get("boundaries", [])]
        else:
            ports_min = expect.get("ports_min", 1)
            by_port = data.get("by_port", {})
            if len(by_port) < ports_min:
                ok = False
                issues.append(f"ports={len(by_port)} < {ports_min}")
            summary = (
                f"boundaries={data['boundary_count']} "
                f"ports={list(by_port.keys())} "
                f"path_kind={data.get('path_kind')}"
            )
            nodes = [data["instance_node"], *data.get("boundaries", [])]

        results.append(
            CheckResult(
                name=name,
                category=kind,
                passed=ok,
                summary=summary,
                issues=issues,
                nodes=nodes,
                tsv=path.name,
            )
        )
    return results


def _conn_checks(root: Path) -> list[CheckResult]:
    conn_path = root / "out_pw_multifan_gen_conn.tsv"
    check_ids = ("pw_deep_gen_clk_port", "pw_deep_gen_if_cell")
    if not conn_path.is_file():
        return [
            CheckResult(
                name=check_id,
                category="conn",
                passed=False,
                summary="missing TSV",
                issues=["missing out_pw_multifan_gen_conn.tsv"],
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
        results.append(
            CheckResult(
                name=check_id,
                category="conn",
                passed=ok,
                summary=f"connected={row['connected']} mode={row['mode']}",
                issues=[] if ok else [f"connected={row['connected']!r}"],
                nodes=[row["endpoint_a_prov"], row["endpoint_b_prov"]],
                tsv=conn_path.name,
            )
        )
    return results


def main() -> int:
    root = Path(__file__).resolve().parent
    results = _cone_io_checks(root) + _conn_checks(root)
    return emit_report(
        "unified_verify multifan",
        results,
        report_path=root / "verify_multifan.report.txt",
    )


if __name__ == "__main__":
    raise SystemExit(main())