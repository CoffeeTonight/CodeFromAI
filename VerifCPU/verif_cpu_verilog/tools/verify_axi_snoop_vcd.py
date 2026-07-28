#!/usr/bin/env python3
"""Post-sim VCD checks for tb_axi_snoop_snq (snoop_valid + pass count)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_amba_bus_vcd import VcdDB, had_value  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
TB = REPO / "tb/tb_axi_snoop_snq.v"
TB_MOD = "tb_axi_snoop_snq"


def expected_pass() -> int:
    body = TB.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"TB_EXPECTED_PASS\s*=\s*(\d+)", body)
    if not m:
        raise RuntimeError(f"{TB}: missing TB_EXPECTED_PASS")
    return int(m.group(1))


def final_int(db: VcdDB, module: str, name: str) -> int | None:
    s = db.series_module(module, name)
    defined = [(t, v) for t, v in s if v is not None]
    return defined[-1][1] if defined else None


def main(argv: list[str]) -> int:
    path = Path(argv[1] if len(argv) > 1 else REPO / "sim_build/tb_axi_snoop_snq.vcd")
    print(f"[vcd] {path} ({path.stat().st_size if path.is_file() else 0} bytes)")
    if not path.is_file():
        print("  [FAIL] missing VCD")
        return 1

    db = VcdDB(path)
    errs: list[str] = []

    want = expected_pass()
    final_pass = final_int(db, TB_MOD, "pass")
    if final_pass is None:
        errs.append("missing pass counter")
    elif final_pass != want:
        errs.append(f"pass={final_pass} expected {want}")

    sn_v = db.series_module(TB_MOD, "sn_v")
    if not sn_v or not had_value(sn_v, 1):
        sn_v = db.series_module("u_mst", "snoop_valid")
        if not sn_v or not had_value(sn_v, 1):
            errs.append("snoop_valid never rose")

    if errs:
        for e in errs:
            print(f"  [FAIL] {e}")
        return 1
    print(f"  [PASS] snoop VCD gates (pass={final_pass}, snoop activity OK)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
