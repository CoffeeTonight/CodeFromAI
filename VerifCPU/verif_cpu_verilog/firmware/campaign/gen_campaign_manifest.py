#!/usr/bin/env python3
"""Generate Master/Agent manifest artifacts from campaign_manifest.h."""

import os
import re
import sys

from manifest_h_parser import parse_slave_rows, parse_master_row, parse_target_blocks
from verilog_paths import CAMPAIGN_ROOT as ROOT, INCLUDE_DIR

HDR = os.path.join(ROOT, "include", "campaign_manifest.h")
OUT_VH = os.path.join(INCLUDE_DIR, "campaign_manifest.vh")

SYM_ADDR = {
    "SFR_CTRL": 0x40000000,
    "SFR_CFG": 0x40000004,
    "SRAM_MARKER": 0x80000000,
    "SRAM_AUX": 0x80000004,
    "UART_BAUD": 0xC0000000,
    "UART_IRQ_HANG": 0xC0000010,
}


def resolve_addr(token: str) -> int:
    token = token.strip()
    if token in SYM_ADDR:
        return SYM_ADDR[token]
    return int(token, 0)


def parse_manifest(path: str) -> tuple[list[dict], dict | None]:
    with open(path, encoding="utf-8") as f:
        body = f.read()

    slaves = parse_slave_rows(body)
    master = parse_master_row(body)
    target_blocks = parse_target_blocks(body)
    targets_by_key = {}
    for key, rows in target_blocks.items():
        targets_by_key[key] = [
            {
                "addr": resolve_addr(row["sym"]),
                "expect": int(row["expect"], 0),
                "icode": row["icode"],
            }
            for row in rows
        ]

    for s in slaves:
        key = f"MANIFEST_{s['name']}_TARGETS"
        s["targets"] = targets_by_key.get(key, [])
        if len(s["targets"]) != s["target_count"]:
            print(f"[manifest] WARN {s['name']}: count mismatch", file=sys.stderr)

    if master:
        key = f"MANIFEST_{master['name']}_TARGETS"
        master["targets"] = targets_by_key.get(key, [])
        master["target_count"] = len(master["targets"])

    return slaves, master


def _emit_hint_lines(slaves: list[dict], master: dict | None) -> tuple[list[str], int]:
    lines: list[str] = []
    idx = 0
    agents = []
    if master and master.get("targets"):
        agents.append(master)
    agents.extend(s for s in slaves if s.get("enabled"))
    for s in agents:
        for t in s["targets"]:
            lines.append(
                f"  $display(\"SCPU0 (MSTR) > hint slave={s['name']} tap={s['tap']} "
                f"addr=0x%08h expect=0x%08h icode=%s\", "
                f"32'h{t['addr']:08X}, 32'h{t['expect']:08X}, \"{t['icode']}\"); \\"
            )
            idx += 1
    return lines, idx


def emit_vh(slaves: list[dict], master: dict | None, path: str) -> None:
    hint_lines, idx = _emit_hint_lines(slaves, master)
    lines = [
        "// Auto-generated from firmware/campaign/include/campaign_manifest.h",
        "`ifndef CAMPAIGN_MANIFEST_VH",
        "`define CAMPAIGN_MANIFEST_VH",
        "",
        f"`define MANIFEST_SLAVE_COUNT {len(slaves)}",
        "",
        "// Master Phase B: inject bus_read per target (TB calls decode_read)",
        "`define CAMPAIGN_MANIFEST_MASTER_LOG \\",
    ]
    lines.extend(hint_lines)
    lines.append("")
    lines.append("`define CAMPAIGN_MANIFEST_BUS_READS \\")
    agents = []
    if master and master.get("targets"):
        agents.append(master)
    agents.extend(s for s in slaves if s.get("enabled"))
    for s in agents:
        for t in s["targets"]:
            lines.append(
                f"  u_soc.decode_read(32'h{t['addr']:08X}, 3'd4, rdata, rresp, rport); \\"
            )
    lines.append("")
    lines.append("// Agent expected_for_addr case arms")
    lines.append("`define CAMPAIGN_MANIFEST_EXPECT_CASES \\")
    seen = set()
    for s in agents:
        for t in s["targets"]:
            if t["addr"] in seen:
                continue
            seen.add(t["addr"])
            lines.append(
                f"        32'h{t['addr']:08X}: expected_for_addr = 32'h{t['expect']:08X}; \\"
            )
    lines += ["", "`endif", ""]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[manifest] Wrote {path} ({idx} master hints)")


def main() -> int:
    slaves, master = parse_manifest(HDR)
    if not slaves and not (master and master.get("targets")):
        print("[manifest] no slave/master targets — emitting empty manifest VH")
        master = None
    emit_vh(slaves, master, OUT_VH)
    return 0


if __name__ == "__main__":
    sys.exit(main())