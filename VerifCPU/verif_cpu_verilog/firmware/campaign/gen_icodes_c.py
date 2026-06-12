#!/usr/bin/env python3
"""Emit probe icode .c sources from probe_icodes.build_catalog_50() (50 total)."""

from __future__ import annotations

import sys
from pathlib import Path

CAMPAIGN_ROOT = Path(__file__).resolve().parent
ICODES_DIR = CAMPAIGN_ROOT / "icodes" / "probe"
TOOLS = CAMPAIGN_ROOT.parent.parent / "tools"
sys.path.insert(0, str(TOOLS))

from probe_icodes import build_catalog_50  # noqa: E402

SKIP = {
    "check_sfr_ctrl", "check_sfr_mask", "check_sram_marker", "check_sram_aux",
    "check_uart_baud", "check_uart_irq",
}


def emit_c(spec) -> str:
    if spec.op == "R":
        body = f"    bus_read32(11, 0x{spec.bus_addr:08X}u);\n    vstop();"
    else:
        body = (
            f"    load_soc_addr(5, 0x{spec.write_data:08X}u);\n"
            f"    bus_write32(5, 0x{spec.bus_addr:08X}u);\n"
            f"    vstop();"
        )
    return (
        '#include "icode.h"\n'
        "\n"
        f"ICODE_ENTRY({spec.name})\n"
        "{\n"
        f"{body}\n"
        "}\n"
    )


def main() -> int:
    ICODES_DIR.mkdir(parents=True, exist_ok=True)
    created = 0
    for spec in build_catalog_50():
        if spec.name in SKIP:
            continue
        path = ICODES_DIR / f"{spec.name}.c"
        text = emit_c(spec)
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8")
            created += 1
    total = len(list(ICODES_DIR.glob("*.c"))) + len(SKIP)
    print(f"[gen_icodes_c] probe/ dir: {len(list(ICODES_DIR.glob('*.c')))} new files "
          f"({created} written), {total} icode sources with manifest set")
    assert len(build_catalog_50()) == 50
    return 0


if __name__ == "__main__":
    raise SystemExit(main())