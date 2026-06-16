#!/usr/bin/env python3
"""Assert zigzag depth + a[2:0][3:0] bus FF/comb trace (path-walk scan-inst)."""

from __future__ import annotations

from pathlib import Path

from verify_report import (
    CheckResult,
    NodeProvenance,
    emit_report,
    parse_conn_tsv,
    parse_cone_tsv,
    parse_io_tsv,
)

DEEP_D5 = "hc_verify_top.u_zigzag.u_deep.d1.d2.d3.d4.d5"
SHALLOW_R4 = "hc_verify_top.u_zigzag.u_shallow.r1.r2.r3.r4"


def _conn_checks(root: Path) -> list[CheckResult]:
    conn_path = root / "out_pw_zigzag_conn.tsv"
    check_ids = (
        "pw_zz_src_to_bus",
        "pw_zz_src_to_deep_a00",
        "pw_zz_deep_to_shallow",
        "pw_zz_deep_to_shallow_slice",
        "pw_zz_shallow_y_bus",
        "pw_zz_deep_y_bus",
        "pw_zz_clk_deep",
        "pw_zz_zigzag_hier",
        "pw_zz_zigzag_shallow_hier",
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
        nodes = [row["endpoint_a_prov"], row["endpoint_b_prov"]]
        results.append(
            CheckResult(
                name=check_id,
                category="conn",
                passed=ok,
                summary=f"connected={row['connected']} mode={row['mode']}",
                issues=[] if ok else [f"connected={row['connected']!r}"],
                nodes=nodes,
                tsv=conn_path.name,
            )
        )
    return results


def _cone_checks(root: Path) -> list[CheckResult]:
    specs = (
        ("fanout_comb", "out_pw_zigzag_fanout_comb.tsv", True),
        ("fanout_ff", "out_pw_zigzag_fanout_ff.tsv", True),
    )
    results: list[CheckResult] = []
    for label, fname, need_ff in specs:
        path = root / fname
        if not path.is_file():
            results.append(
                CheckResult(
                    name=label,
                    category="cone",
                    passed=False,
                    summary="missing TSV",
                    issues=[f"missing {fname}"],
                    tsv=fname,
                )
            )
            continue
        data = parse_cone_tsv(path)
        ok = True
        issues: list[str] = []
        if data.get("origin") != f"{DEEP_D5}.a[0][0]":
            ok = False
            issues.append(f"origin={data.get('origin')}")
        if data["boundary_count"] < 1:
            ok = False
            issues.append("no boundaries")
        if need_ff and "ff-sink" not in data.get("kinds", []):
            ok = False
            issues.append(f"kinds={data.get('kinds')}")
        nodes = [data["origin_node"], *data.get("boundaries", [])]
        results.append(
            CheckResult(
                name=label,
                category="cone",
                passed=ok,
                summary=(
                    f"boundaries={data['boundary_count']} "
                    f"origin={data.get('origin')}"
                ),
                issues=issues,
                nodes=nodes,
                tsv=fname,
            )
        )
    return results


def _io_checks(root: Path) -> list[CheckResult]:
    specs = (
        ("io_driver_comb", "out_pw_zigzag_io_driver_comb.tsv", DEEP_D5, True, 10),
        ("io_driver_ff", "out_pw_zigzag_io_driver_ff.tsv", DEEP_D5, True, 10),
        ("io_sinker_comb", "out_pw_zigzag_io_sinker_comb.tsv", DEEP_D5, False, 1),
        (
            "io_shallow_driver",
            "out_pw_zigzag_io_shallow_driver.tsv",
            SHALLOW_R4,
            True,
            5,
        ),
    )
    results: list[CheckResult] = []
    for label, fname, instance, need_bus_alias, min_boundaries in specs:
        path = root / fname
        if not path.is_file():
            results.append(
                CheckResult(
                    name=label,
                    category="io",
                    passed=False,
                    summary="missing TSV",
                    issues=[f"missing {fname}"],
                    tsv=fname,
                )
            )
            continue
        data = parse_io_tsv(path)
        ok = True
        issues: list[str] = []
        if data.get("instance") != instance:
            ok = False
            issues.append(f"instance={data.get('instance')}")
        if data["boundary_count"] < min_boundaries:
            ok = False
            issues.append(f"boundary_count={data['boundary_count']}")
        if need_bus_alias and "a[2:0][3:0]" not in data.get("origin_ports", set()):
            ok = False
            issues.append(
                "origin_ports missing a[2:0][3:0]: "
                f"{sorted(data.get('origin_ports', []))[:8]}"
            )
        if label == "io_sinker_comb" and "port-out" not in data.get("kinds", []):
            ok = False
            issues.append(f"kinds={data.get('kinds')}")
        if label == "io_shallow_driver" and not any(
            "u_shallow" in s for s in data.get("scopes", [])
        ):
            ok = False
            issues.append(f"scopes={data.get('scopes', [])}")
        nodes: list[NodeProvenance] = [data["instance_node"]]
        nodes.extend(data.get("boundaries", []))
        results.append(
            CheckResult(
                name=label,
                category="io",
                passed=ok,
                summary=(
                    f"boundaries={data['boundary_count']} "
                    f"bus_alias={'a[2:0][3:0]' in data.get('origin_ports', set())}"
                ),
                issues=issues,
                nodes=nodes,
                tsv=fname,
            )
        )
    return results


def main() -> int:
    root = Path(__file__).resolve().parent
    results = _conn_checks(root) + _cone_checks(root) + _io_checks(root)
    return emit_report(
        "unified_verify zigzag bus",
        results,
        report_path=root / "verify_zigzag_bus.report.txt",
    )


if __name__ == "__main__":
    raise SystemExit(main())