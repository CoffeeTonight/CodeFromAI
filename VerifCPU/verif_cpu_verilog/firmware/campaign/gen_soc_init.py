#!/usr/bin/env python3
"""Generate SoC init sequences for Verilog + Python from soc_init_seq.h."""

import os
import re
import sys

from verilog_paths import CAMPAIGN_ROOT as ROOT, INCLUDE_DIR

HDR = os.path.join(ROOT, "include", "soc_init_seq.h")
PLATFORM_HDR = os.path.join(ROOT, "include", "soc_platform.h")
OUT_VH = os.path.join(INCLUDE_DIR, "soc_init_seq.vh")
OUT_PLATFORM_VH = os.path.join(INCLUDE_DIR, "campaign_soc_platform.vh")

SYM_ADDR = {
    "SFR_CTRL": 0x40000000,
    "SFR_CFG": 0x40000004,
    "SFR_CLK": 0x40000008,
    "SFR_INT_EN": 0x4000000C,
    "SFR_DMA_SRC": 0x40000010,
    "SFR_DMA_DST": 0x40000014,
    "SFR_STATUS": 0x40000018,
    "SFR_GPIO_DIR": 0x4000001C,
    "SFR_GPIO_OUT": 0x40000020,
    "SFR_GPIO_IN": 0x40000024,
    "SRAM_MARKER": 0x80000000,
    "SRAM_AUX": 0x80000004,
    "UART_BAUD": 0xC0000000,
    "UART_IRQ_HANG": 0xC0000010,
}


def parse_platform(path: str) -> dict[str, int]:
    with open(path, encoding="utf-8") as f:
        body = f.read()

    def _val(name: str) -> int:
        m = re.search(rf"#define\s+{name}\s+(0x[0-9a-fA-F]+|\w+)", body)
        if not m:
            raise ValueError(f"missing {name} in {path}")
        tok = m.group(1)
        if tok in SYM_ADDR:
            return SYM_ADDR[tok]
        return int(tok, 0)

    return {
        "addr": _val("SOC_INIT_DONE_ADDR"),
        "mask": _val("SOC_INIT_DONE_MASK"),
        "value": _val("SOC_INIT_DONE_VALUE"),
    }


def emit_platform_vh(cfg: dict[str, int], path: str) -> None:
    lines = [
        "// Auto-generated from firmware/campaign/include/soc_platform.h",
        "`ifndef CAMPAIGN_SOC_PLATFORM_VH",
        "`define CAMPAIGN_SOC_PLATFORM_VH",
        "",
        f"`define CAMPAIGN_SOC_INIT_DONE_ADDR  32'h{cfg['addr']:08X}",
        f"`define CAMPAIGN_SOC_INIT_DONE_MASK  32'h{cfg['mask']:08X}",
        f"`define CAMPAIGN_SOC_INIT_DONE_VALUE 32'h{cfg['value']:08X}",
        "",
        "`define CAMPAIGN_MASTER_INSTANCE \\",
        "  verif_agent_master #( \\",
        "    .CPU_ID(0), \\",
        "    .INIT_DONE_ADDR(`CAMPAIGN_SOC_INIT_DONE_ADDR), \\",
        "    .INIT_DONE_MASK(`CAMPAIGN_SOC_INIT_DONE_MASK), \\",
        "    .INIT_DONE_VALUE(`CAMPAIGN_SOC_INIT_DONE_VALUE) \\",
        "  ) u_mstr ();",
        "",
        "`endif",
        "",
    ]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[gen_soc_init] Wrote {path} (init_done @ 0x{cfg['addr']:08X})")


def parse_header(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        body = f.read()
    steps = []
    hex_tok = r"(0x[0-9a-fA-F]+u?|0u|[A-Z0-9_]+)"
    pat = rf"\{{\s*SOC_INIT_OP_(\w+)\s*,\s*([A-Z0-9_]+)\s*,\s*{hex_tok}\s*,\s*{hex_tok}\s*\}}"
    platform_tokens = {
        "SOC_INIT_DONE_ADDR": None,
        "SOC_INIT_DONE_MASK": None,
        "SOC_INIT_DONE_VALUE": None,
    }

    def _tok_int(tok: str, platform: dict[str, int] | None) -> int:
        if tok in SYM_ADDR:
            return SYM_ADDR[tok]
        if tok in platform_tokens and platform is not None:
            key = tok.replace("SOC_INIT_DONE_", "").lower()
            if key == "addr":
                return platform["addr"]
            if key == "mask":
                return platform["mask"]
            if key == "value":
                return platform["value"]
        return int(tok.rstrip("u"), 0)

    platform_cfg: dict[str, int] | None = None
    if os.path.isfile(PLATFORM_HDR):
        platform_cfg = parse_platform(PLATFORM_HDR)

    for m in re.finditer(pat, body):
        steps.append({
            "op": 0 if m.group(1) == "WRITE" else 1,
            "sym": m.group(2),
            "wdata": _tok_int(m.group(3), platform_cfg),
            "expect": _tok_int(m.group(4), platform_cfg),
        })
    return steps


def emit_vh(steps: list[dict], path: str) -> None:
    lines = [
        "// Auto-generated from firmware/campaign/include/soc_init_seq.h",
        "`ifndef SOC_INIT_SEQ_VH",
        "`define SOC_INIT_SEQ_VH",
        "",
        f"`define SOC_INIT_STEP_COUNT {len(steps)}",
        "",
        "// Include inside simple_soc run_init — uses decode_write/decode_read/r/p/rd",
        "`define SOC_INIT_RUN_STEPS \\",
    ]
    for i, s in enumerate(steps):
        addr = SYM_ADDR[s["sym"]]
        if s["op"] == 0:
            lines.append(
                f"  decode_write(32'h{addr:08X}, 32'h{s['wdata']:08X}, 3'd4, r, p); \\"
            )
        else:
            lines.append(f"  decode_read(32'h{addr:08X}, 3'd4, rd, r, p); \\")
            lines.append(
                "  if (rd !== 32'h{exp:08X}) "
                "$display(\"[SoC] init read mismatch @0x%08h got=0x%08h expect=0x%08h\", "
                "32'h{addr:08X}, rd, 32'h{exp:08X}); \\".format(exp=s["expect"], addr=addr)
            )
    lines += ["", "`endif", ""]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[gen_soc_init] Wrote {path} ({len(steps)} steps)")


def emit_platform_py(cfg: dict[str, int], path: str) -> None:
    lines = [
        '"""Auto-generated from firmware/campaign/include/soc_platform.h."""',
        "",
        f"INIT_DONE_ADDR = 0x{cfg['addr']:08X}",
        f"INIT_DONE_MASK = 0x{cfg['mask']:08X}",
        f"INIT_DONE_VALUE = 0x{cfg['value']:08X}",
        "INIT_DONE_POLL_MAX = 4096",
        "",
        "",
        "def init_done_met(val: int) -> bool:",
        "    return (val & INIT_DONE_MASK) == INIT_DONE_VALUE",
        "",
    ]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[gen_soc_init] Wrote {path}")


def emit_py(steps: list[dict], path: str) -> None:
    lines = [
        '"""Auto-generated from firmware/campaign/include/soc_init_seq.h."""',
        "",
        "SOC_INIT_STEPS = [",
    ]
    for s in steps:
        addr = SYM_ADDR[s["sym"]]
        if s["op"] == 0:
            lines.append(f'    ("write", 0x{addr:08X}, 0x{s["wdata"]:08X}, 4),')
        else:
            lines.append(f'    ("read", 0x{addr:08X}, 0x{s["expect"]:08X}, 4),')
    lines.append("]")
    lines.append("")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[gen_soc_init] Wrote {path}")


def main() -> int:
    steps = parse_header(HDR)
    if not steps:
        print("[gen_soc_init] failed to parse steps", file=sys.stderr)
        return 1
    platform = parse_platform(PLATFORM_HDR)
    emit_vh(steps, OUT_VH)
    emit_platform_vh(platform, OUT_PLATFORM_VH)
    return 0


if __name__ == "__main__":
    sys.exit(main())