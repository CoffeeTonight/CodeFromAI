#!/usr/bin/env python3
"""Generate Master/Agent manifest artifacts from campaign_manifest.h."""

import os
import re
import sys

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


def parse_manifest(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        body = f.read()

    slaves = []
    for m in re.finditer(
        r'\{\s*"([^"]+)"\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*POOL_WORD_\w+\s*,\s*(\d+)\s*\}',
        body,
    ):
        slaves.append({
            "name": m.group(1),
            "cpu_id": int(m.group(2)),
            "tap": int(m.group(3)),
            "target_count": int(m.group(4)),
        })

    target_blocks = re.findall(
        r"static const manifest_target_t (MANIFEST_\w+_TARGETS)\[\] = \{(.*?)\};",
        body,
        re.S,
    )
    targets_by_key = {}
    for key, block in target_blocks:
        entries = []
        for row in re.finditer(
            r"\{\s*([A-Z0-9_]+)\s*,\s*(0x[0-9a-fA-F]+)u?\s*,\s*\"([^\"]+)\"\s*\}",
            block,
        ):
            entries.append({
                "addr": resolve_addr(row.group(1)),
                "expect": int(row.group(2), 0),
                "icode": row.group(3),
            })
        targets_by_key[key] = entries

    name_to_key = {"SFR": "MANIFEST_SFR_TARGETS", "SRAM": "MANIFEST_SRAM_TARGETS", "UART": "MANIFEST_UART_TARGETS"}
    for s in slaves:
        s["targets"] = targets_by_key.get(name_to_key[s["name"]], [])
        if len(s["targets"]) != s["target_count"]:
            print(f"[manifest] WARN {s['name']}: count mismatch", file=sys.stderr)
    return slaves


def emit_vh(slaves: list[dict], path: str) -> None:
    lines = [
        "// Auto-generated from firmware/campaign/include/campaign_manifest.h",
        "`ifndef CAMPAIGN_MANIFEST_VH",
        "`define CAMPAIGN_MANIFEST_VH",
        "",
        f"`define MANIFEST_SLAVE_COUNT {len(slaves)}",
        "",
        "// Master Phase B: inject bus_read per slave target (TB calls decode_read)",
        "`define CAMPAIGN_MANIFEST_MASTER_LOG \\",
    ]
    idx = 0
    for s in slaves:
        for t in s["targets"]:
            lines.append(
                f"  $display(\"SCPU0 (MSTR) > hint slave={s['name']} tap={s['tap']} "
                f"addr=0x%08h expect=0x%08h icode=%s\", "
                f"32'h{t['addr']:08X}, 32'h{t['expect']:08X}, \"{t['icode']}\"); \\"
            )
            idx += 1
    lines.append("")
    lines.append("`define CAMPAIGN_MANIFEST_BUS_READS \\")
    for s in slaves:
        for t in s["targets"]:
            lines.append(
                f"  u_soc.decode_read(32'h{t['addr']:08X}, 3'd4, rdata, rresp, rport); \\"
            )
    lines.append("")
    lines.append("// Agent expected_for_addr case arms")
    lines.append("`define CAMPAIGN_MANIFEST_EXPECT_CASES \\")
    seen = set()
    for s in slaves:
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


def emit_py(slaves: list[dict], path: str) -> None:
    lines = [
        '"""Auto-generated from firmware/campaign/include/campaign_manifest.h."""',
        "",
        "VERIFY_MANIFEST = [",
    ]
    for s in slaves:
        lines.append("    {")
        lines.append(f'        "name": "{s["name"]}",')
        lines.append(f'        "cpu_id": {s["cpu_id"]},')
        lines.append(f'        "tap_port": {s["tap"]},')
        lines.append('        "targets": [')
        for t in s["targets"]:
            lines.append("            {")
            lines.append(f'                "addr": 0x{t["addr"]:08X},')
            lines.append(f'                "expect": 0x{t["expect"]:08X},')
            lines.append(f'                "icode": "{t["icode"]}",')
            lines.append("            },")
        lines.append("        ],")
        lines.append("    },")
    lines.append("]")
    lines.append("")
    lines.append("")
    lines.append("def hints_for_slave(name: str) -> list[int]:")
    lines.append('    """Addresses Master must inject for this slave."""')
    lines.append("    for s in VERIFY_MANIFEST:")
    lines.append('        if s["name"] == name:')
    lines.append('            return [t["addr"] for t in s["targets"]]')
    lines.append("    return []")
    lines.append("")
    lines.append("")
    lines.append("def all_master_hints() -> list[tuple[str, int, int, str]]:")
    lines.append('    """(slave_name, addr, expect, icode) in Master injection order."""')
    lines.append("    out = []")
    lines.append("    for s in VERIFY_MANIFEST:")
    lines.append('        for t in s["targets"]:')
    lines.append('            out.append((s["name"], t["addr"], t["expect"], t["icode"]))')
    lines.append("    return out")
    lines.append("")
    lines.append("")
    lines.append("def icode_bind_by_tap() -> dict[int, list[str]]:")
    lines.append("    return {s['tap_port']: [t['icode'] for t in s['targets']] for s in VERIFY_MANIFEST}")
    lines.append("")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[manifest] Wrote {path}")


def main() -> int:
    slaves = parse_manifest(HDR)
    if not slaves:
        print("[manifest] parse failed", file=sys.stderr)
        return 1
    emit_vh(slaves, OUT_VH)
    return 0


if __name__ == "__main__":
    sys.exit(main())