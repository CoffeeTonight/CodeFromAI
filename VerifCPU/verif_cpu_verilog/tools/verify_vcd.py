#!/usr/bin/env python3
"""Post-sim VCD checks for full campaign (authoritative verification gate)."""

import os
import re
import sys

DEAD_HEX = 0xDEADDEAD
DEAD_BIN = format(DEAD_HEX, "032b")
DEAD_HEX_MARKERS = ("deaddead",)


def _is_valid_vcd_header(body: str) -> bool:
    return "$enddefinitions" in body and "$scope" in body


def _final_signal_value(body: str, sig_id: str) -> str | None:
    """Return last binary value assigned to VCD signal id (e.g. '7')."""
    last: str | None = None
    pat = re.compile(rf"^b([01xzXZ]+) {re.escape(sig_id)}$", re.MULTILINE)
    for m in pat.finditer(body):
        last = m.group(1)
    return last


def verify_main_vcd(path: str) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not os.path.isfile(path):
        return False, [f"missing VCD: {path}"]

    size = os.path.getsize(path)
    if size < 128:
        errors.append(f"VCD too small ({size} bytes): {path}")

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        body = f.read()

    if not _is_valid_vcd_header(body):
        errors.append("not a valid VCD (no $scope / $enddefinitions)")

    if "tb_full_campaign" not in body:
        errors.append("VCD missing tb_full_campaign hierarchy")

    if "vcd_marker" not in body:
        errors.append("VCD missing vcd_marker signal (campaign pass stamp)")
    else:
        m = re.search(r"\$var reg 32 (\S+) vcd_marker", body)
        if m:
            marker_val = _final_signal_value(body, m.group(1))
            if marker_val is None:
                errors.append("vcd_marker never toggled in VCD timeline")
            elif marker_val != DEAD_BIN:
                errors.append(
                    f"vcd_marker final value {marker_val!r} != 0xDEADDEAD "
                    f"(expected {DEAD_BIN})"
                )
        else:
            errors.append("could not parse vcd_marker signal id")

    has_dead_wave = DEAD_BIN in body or any(m in body.lower() for m in DEAD_HEX_MARKERS)
    if not has_dead_wave:
        errors.append(
            "VCD missing 0xDEADDEAD wave data — confirm dummy/X-Z/recovery in GTKWave"
        )

    # Orchestrator reset pulses (phase + icode inter-reset)
    m = re.search(r"\$var (?:wire|reg) 32 (\S+) orch_reset_count", body)
    if m:
        rst_val = _final_signal_value(body, m.group(1))
        if rst_val is None or int(rst_val.replace("x", "0").replace("z", "0"), 2) < 4:
            errors.append("orch_reset_count < 4 (missing icode inter-reset / phase resets)")
    else:
        errors.append("VCD missing orch_reset_count")

    # Agent verify_pass sum (3 agents × 2 icode slots = 6)
    pass_ids = re.findall(r"\$var reg 32 (\S+) verify_pass", body)
    if len(pass_ids) >= 3:
        total_pass = 0
        for sid in pass_ids[:3]:
            v = _final_signal_value(body, sid)
            if v:
                total_pass += int(v.replace("x", "0").replace("z", "0"), 2)
        if total_pass < 6:
            errors.append(f"agent verify_pass sum={total_pass} (expected 6 multi-icode)")
    else:
        errors.append("VCD missing agent verify_pass signals")

    return len(errors) == 0, errors


def verify_cpu_vcd(path: str) -> tuple[bool, list[str]]:
    """Per-CPU hierarchical export (TOP scope, pc/x regs)."""
    errors: list[str] = []
    if not os.path.isfile(path):
        return False, [f"missing VCD: {path}"]

    size = os.path.getsize(path)
    if size < 64:
        errors.append(f"VCD too small ({size} bytes): {path}")

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        body = f.read()

    if not _is_valid_vcd_header(body):
        errors.append("not a valid VCD (no $scope / $enddefinitions)")

    if "$scope module TOP" not in body:
        errors.append("per-CPU VCD missing TOP scope")

    if " pc " not in body and "$var reg" not in body:
        errors.append("per-CPU VCD missing pc register dump")

    return len(errors) == 0, errors


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: verify_vcd.py <main.vcd> [per-cpu.vcd ...]")
        return 2

    ok_all = True
    main_vcd = argv[1]
    ok, errs = verify_main_vcd(main_vcd)
    if ok:
        print(f"[PASS] Main VCD OK: {main_vcd} ({os.path.getsize(main_vcd)} bytes)")
        print(f"       vcd_marker=0xDEADDEAD confirmed")
    else:
        ok_all = False
        print(f"[FAIL] Main VCD: {main_vcd}")
        for e in errs:
            print(f"       - {e}")

    for p in argv[2:]:
        if not os.path.isfile(p):
            print(f"[SKIP] Optional per-CPU VCD not found: {p}")
            continue
        ok, errs = verify_cpu_vcd(p)
        if ok:
            print(f"[PASS] CPU VCD OK: {p} ({os.path.getsize(p)} bytes)")
        else:
            ok_all = False
            print(f"[FAIL] CPU VCD: {p}")
            for e in errs:
                print(f"       - {e}")

    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))