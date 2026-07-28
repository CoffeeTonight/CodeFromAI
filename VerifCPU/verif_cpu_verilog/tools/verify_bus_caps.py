#!/usr/bin/env python3
"""Check // tool: cap_* tags in bus RTL against amba_bus_registry caps SSOT.

Exit 0 if every registry rtl_module with caps has a matching tool tag line
in rtl/<module>.v (cap names present as cap_name=0 or =1). Missing or
contradictory positive caps fail the check.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "firmware" / "campaign"))

from amba_bus_registry import (  # noqa: E402
    CAP_BLOCKING_OS,
    CAP_MULTI_OS,
    CAP_SMOKE_ONLY,
    CAP_SPLIT_RW,
    expected_tool_caps_by_rtl_module,
)

# Explicit =0 means the cap is intentionally absent (not a failure if registry
# does not list it; if registry lists a positive cap, =0 is a fail).
TOOL_CAP_RE = re.compile(r"//\s*tool:\s*(.+)")
CAP_TOKEN_RE = re.compile(r"(cap_[a-z0-9_]+)\s*=\s*([01])")

# Extra modules not in BUS_TYPES but still tagged (local mem / soc decode).
EXTRA_MODULE_CAPS: dict[str, frozenset[str]] = {
    "verif_cpu_bus": frozenset({CAP_BLOCKING_OS}),
    "verif_soc_bus": frozenset({CAP_BLOCKING_OS}),
}


def parse_tool_caps(text: str) -> dict[str, int]:
    found: dict[str, int] = {}
    for line in text.splitlines():
        m = TOOL_CAP_RE.search(line)
        if not m:
            continue
        for name, val in CAP_TOKEN_RE.findall(m.group(1)):
            found[name] = int(val)
    return found


def check_module(module: str, expected: frozenset[str]) -> list[str]:
    path = ROOT / "rtl" / f"{module}.v"
    errs: list[str] = []
    if not path.is_file():
        return [f"{module}: missing rtl/{module}.v"]
    caps = parse_tool_caps(path.read_text(encoding="utf-8", errors="replace"))
    if not caps and expected:
        return [f"{module}: no // tool: cap_* line (expected {sorted(expected)})"]
    for cap in sorted(expected):
        if cap not in caps:
            errs.append(f"{module}: missing tool tag {cap}=1 (registry expects it)")
        elif caps[cap] != 1:
            errs.append(f"{module}: tool has {cap}={caps[cap]} but registry expects 1")
    # Multi-OS and blocking-OS are mutually exclusive when both tagged
    if caps.get(CAP_MULTI_OS) == 1 and caps.get(CAP_BLOCKING_OS) == 1:
        errs.append(f"{module}: both {CAP_MULTI_OS}=1 and {CAP_BLOCKING_OS}=1")
    if CAP_SMOKE_ONLY in expected and CAP_SPLIT_RW in caps and caps[CAP_SPLIT_RW] == 1:
        # smoke-only may still claim split in future; ignore
        pass
    return errs


def main() -> int:
    expected = expected_tool_caps_by_rtl_module()
    for mod, caps in EXTRA_MODULE_CAPS.items():
        expected[mod] = expected.get(mod, frozenset()) | caps

    all_errs: list[str] = []
    for module in sorted(expected):
        all_errs.extend(check_module(module, expected[module]))

    if all_errs:
        print("verify_bus_caps: FAIL")
        for e in all_errs:
            print(f"  {e}")
        return 1
    print(f"verify_bus_caps: OK ({len(expected)} modules with registry/tool caps)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
