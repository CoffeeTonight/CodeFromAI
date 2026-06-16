#!/usr/bin/env python3
"""Assert path-walk on multi-dim instance arrays: a.b.c[0][1].d.e.f[1].g[0][2]."""

from __future__ import annotations

import sys
from pathlib import Path

DEEP_A = "hc_verify_top.u_md2d.a.b.c[0][1].d.e.f[1].g[0][2]"
DEEP_B = "hc_verify_top.u_md2d.a2.b.c[1][0].d.e.f[0].g[1][1]"


def parse_conn_tsv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or line.startswith("check_id"):
            continue
        parts = line.split("\t")
        if parts:
            out[parts[0]] = parts[3] if len(parts) > 3 else ""
    return out


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
        "scopes": scopes,
        "port_count": int(meta.get("port_count", "0")),
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
    scopes = [r[3] for r in boundaries if len(r) > 3]
    return {
        **meta,
        "boundary_count": len(boundaries),
        "scopes": scopes,
    }


def _scopes_match(scopes: list[str], needles: tuple[str, ...], *, min_hits: int) -> bool:
    hits = sum(1 for n in needles if any(n in s for s in scopes))
    return hits >= min_hits


def main() -> int:
    root = Path(__file__).resolve().parent
    failed = 0

    conn_path = root / "out_pw_md2d_conn.tsv"
    if not conn_path.is_file():
        print(f"FAIL conn: missing {conn_path.name}")
        failed += 1
    else:
        conn = parse_conn_tsv(conn_path)
        for check_id in (
            "pw_md2d_hier",
            "pw_md2d_clk",
            "pw_md2d_branch_link",
            "pw_md2d_src_to_a",
            "pw_md2d_b_to_sink",
        ):
            if conn.get(check_id) != "True":
                print(f"FAIL conn: {check_id}={conn.get(check_id)!r}")
                failed += 1
            else:
                print(f"PASS conn: {check_id}=True")

    fanin_path = root / "out_pw_md2d_fanin_clk.tsv"
    if not fanin_path.is_file():
        print(f"FAIL fanin: missing {fanin_path.name}")
        failed += 1
    else:
        data = parse_cone_tsv(fanin_path)
        ok = True
        msgs: list[str] = []
        if data.get("origin") != f"{DEEP_A}.clk":
            ok = False
            msgs.append(f"origin={data.get('origin')}")
        if data["boundary_count"] < 1:
            ok = False
            msgs.append(f"boundary_count={data['boundary_count']}")
        needles = ("c[0][1]", "f[1]", "g[0][2]")
        if not _scopes_match(data.get("scopes", []), needles, min_hits=2):
            ok = False
            msgs.append(f"scopes need 2 of {needles}; got {data.get('scopes', [])}")
        if ok:
            print(
                f"PASS fanin: boundaries={data['boundary_count']} "
                f"origin={data.get('origin')}"
            )
        else:
            failed += 1
            print(f"FAIL fanin: {'; '.join(msgs)}")

    io_path = root / "out_pw_md2d_io_driver.tsv"
    if not io_path.is_file():
        print(f"FAIL io: missing {io_path.name}")
        failed += 1
    else:
        data = parse_io_tsv(io_path)
        ok = True
        msgs: list[str] = []
        if data.get("instance") != DEEP_A:
            ok = False
            msgs.append(f"instance={data.get('instance')}")
        if data["boundary_count"] < 1:
            ok = False
            msgs.append(f"boundary_count={data['boundary_count']}")
        if not _scopes_match(data.get("scopes", []), ("g[0][2]", "c[0][1]"), min_hits=1):
            ok = False
            msgs.append(f"scopes={data.get('scopes', [])}")
        if ok:
            print(f"PASS io: boundaries={data['boundary_count']} instance={DEEP_A}")
        else:
            failed += 1
            print(f"FAIL io: {'; '.join(msgs)}")

    if not failed:
        print(
            f"OK md2d path-walk: branch A {DEEP_A} <-> branch B {DEEP_B} linked"
        )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())