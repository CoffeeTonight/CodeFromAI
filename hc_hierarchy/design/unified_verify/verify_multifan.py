#!/usr/bin/env python3
"""Assert multi-boundary fanin/fanout + generate paths (full-index and path-walk)."""

from __future__ import annotations

import sys
from pathlib import Path


def parse_cone_tsv(path: Path) -> dict:
    meta: dict[str, str] = {}
    rows: list[list[str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        if line.startswith("#"):
            parts = line[1:].split("\t", 1)
            if len(parts) == 2:
                meta[parts[0].strip()] = parts[1].strip()
            continue
        rows.append(line.split("\t"))
    data_rows = rows[1:] if len(rows) > 1 else []
    scopes = [r[1] for r in data_rows if len(r) > 1]
    return {
        **meta,
        "boundary_count": len(data_rows),
        "kinds": [r[0] for r in data_rows],
        "scopes": scopes,
    }


def parse_io_tsv(path: Path) -> dict:
    meta: dict[str, str] = {}
    rows: list[list[str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        if line.startswith("#"):
            parts = line[1:].split("\t", 1)
            if len(parts) == 2:
                meta[parts[0].strip()] = parts[1].strip()
            continue
        rows.append(line.split("\t"))
    boundaries = rows[1:] if len(rows) > 1 else []
    by_port: dict[str, int] = {}
    scopes: list[str] = []
    for row in boundaries:
        if not row:
            continue
        by_port[row[0]] = by_port.get(row[0], 0) + 1
        if len(row) > 3:
            scopes.append(row[3])
    return {
        **meta,
        "boundary_count": len(boundaries),
        "by_port": by_port,
        "scopes": scopes,
    }


def parse_conn_tsv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or line.startswith("check_id"):
            continue
        parts = line.split("\t")
        if parts:
            out[parts[0]] = parts[3] if len(parts) > 3 else ""
    return out


def _scopes_match(scopes: list[str], needles: tuple[str, ...], *, min_hits: int) -> bool:
    hits = sum(
        1
        for needle in needles
        if any(needle in scope for scope in scopes)
    )
    return hits >= min_hits


def main() -> int:
    root = Path(__file__).resolve().parent
    checks: list[tuple[str, Path, str, dict]] = [
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

    failed = 0
    for name, path, kind, expect in checks:
        if not path.is_file():
            print(f"FAIL {name}: missing {path.name}")
            failed += 1
            continue
        data = parse_io_tsv(path) if kind == "io" else parse_cone_tsv(path)
        ok = True
        msgs: list[str] = []

        bmin = expect.get("boundary_count_min", 2)
        if data["boundary_count"] < bmin:
            ok = False
            msgs.append(f"boundary_count={data['boundary_count']} < {bmin}")

        gen_needles = expect.get("generate_scopes")
        if gen_needles:
            gmin = expect.get("generate_min", 1)
            if not _scopes_match(data.get("scopes", []), gen_needles, min_hits=gmin):
                ok = False
                msgs.append(
                    f"generate scopes need {gmin} of {gen_needles}; got {data.get('scopes', [])[:6]}"
                )

        if kind == "cone":
            pmin = expect.get("port_count_min", 2)
            if int(data.get("port_count", "0")) < pmin:
                ok = False
                msgs.append(f"port_count={data.get('port_count')} < {pmin}")
            summary = (
                f"boundaries={data['boundary_count']} "
                f"port_count={data.get('port_count')} "
                f"direction={data.get('direction')}"
            )
        else:
            ports_min = expect.get("ports_min", 1)
            by_port = data.get("by_port", {})
            if len(by_port) < ports_min:
                ok = False
                msgs.append(f"ports={len(by_port)} < {ports_min}")
            summary = (
                f"boundaries={data['boundary_count']} "
                f"ports={list(by_port.keys())} "
                f"path_kind={data.get('path_kind')}"
            )

        if ok:
            print(f"PASS {name}: {summary}")
        else:
            failed += 1
            print(f"FAIL {name}: {'; '.join(msgs)} | {summary}")

    conn_path = root / "out_pw_multifan_gen_conn.tsv"
    if not conn_path.is_file():
        print("FAIL pw_gen_conn: missing out_pw_multifan_gen_conn.tsv")
        failed += 1
    else:
        conn = parse_conn_tsv(conn_path)
        for check_id in ("pw_deep_gen_clk_port", "pw_deep_gen_if_cell"):
            if conn.get(check_id) != "True":
                print(f"FAIL pw_gen_conn: {check_id}={conn.get(check_id)!r}")
                failed += 1
            else:
                print(f"PASS pw_gen_conn: {check_id}=True")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())