#!/usr/bin/env python3
"""Post-sim VCD checks for full campaign (authoritative verification gate)."""

from __future__ import annotations

import os
import re
import sys

DEAD_HEX = 0xDEADDEAD
DEAD_BIN = format(DEAD_HEX, "032b")
DEAD_HEX_MARKERS = ("deaddead",)

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
INCLUDE = os.path.join(REPO_ROOT, "include")
LOG_FULL = os.environ.get("LOG_FULL", os.path.join(REPO_ROOT, "logs", "full_campaign"))


def _read_include(name: str) -> str:
    path = os.path.join(INCLUDE, name)
    if not os.path.isfile(path):
        return ""
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def _define_int(body: str, macro: str, default: int) -> int:
    m = re.search(rf"`define\s+{re.escape(macro)}\s+(\d+)", body)
    return int(m.group(1)) if m else default


def campaign_expectations() -> tuple[int, int, list[str]]:
    """Return (min_agent_pass_signals, min_verify_pass_sum, per_cpu_vcd_paths)."""
    params = _read_include("campaign_params.vh")
    master = _read_include("campaign_master.vh")
    tb_gen = _read_include("tb_full_campaign_gen.vh")

    num_scpu = _define_int(params, "CAMPAIGN_NUM_SCPU", 3)
    master_vcpu = _define_int(master, "CAMPAIGN_MASTER_VCPU_ENABLED", 0)
    total_pass = _define_int(tb_gen, "CAMPAIGN_TOTAL_ICODE_PASS", 6)
    max_icode_slots = _define_int(tb_gen, "CAMPAIGN_MAX_ICODE_SLOTS", 2)

    min_agents = num_scpu + (1 if master_vcpu else 0)
    if min_agents == 0:
        min_orch_resets = 2
    else:
        min_agents = max(min_agents, 1)
        min_orch_resets = 3 + max(0, max_icode_slots - 1)

    cpu_vcds: list[str] = []
    if master_vcpu:
        cpu_vcds.append(os.path.join(LOG_FULL, "SCPU0.vcd"))
    for cid in range(1, num_scpu + 1):
        cpu_vcds.append(os.path.join(LOG_FULL, f"SCPU{cid}.vcd"))

    return min_agents, total_pass, min_orch_resets, cpu_vcds


def _is_valid_vcd_header(body: str) -> bool:
    return "$enddefinitions" in body and "$scope" in body


def _final_signal_value(body: str, sig_id: str) -> str | None:
    """Return last binary value assigned to VCD signal id (e.g. '7')."""
    last: str | None = None
    pat = re.compile(rf"^b([01xzXZ]+) {re.escape(sig_id)}$", re.MULTILINE)
    for m in pat.finditer(body):
        last = m.group(1)
    return last


def verify_main_vcd(
    path: str,
    *,
    min_agents: int = 3,
    min_pass_sum: int = 6,
    min_orch_resets: int = 4,
) -> tuple[bool, list[str]]:
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
        rst_n = int(rst_val.replace("x", "0").replace("z", "0"), 2) if rst_val else 0
        if rst_val is None or rst_n < min_orch_resets:
            errors.append(
                f"orch_reset_count < {min_orch_resets} "
                f"(missing icode inter-reset / phase resets)"
            )
    else:
        errors.append("VCD missing orch_reset_count")

    pass_ids = re.findall(r"\$var reg 32 (\S+) verify_pass", body)
    if min_agents == 0:
        pass
    elif len(pass_ids) >= min_agents:
        total_pass = 0
        for sid in pass_ids[:min_agents]:
            v = _final_signal_value(body, sid)
            if v:
                total_pass += int(v.replace("x", "0").replace("z", "0"), 2)
        if total_pass < min_pass_sum:
            errors.append(
                f"agent verify_pass sum={total_pass} "
                f"(expected >={min_pass_sum} multi-icode)"
            )
    else:
        errors.append(
            f"VCD missing agent verify_pass signals "
            f"(found {len(pass_ids)}, need >={min_agents})"
        )

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

    if "$scope module TOP" not in body and "$scope module SCPU" not in body:
        errors.append("per-CPU VCD missing CPU scope (TOP or SCPU<n>)")

    if " pc " not in body and "$var reg" not in body:
        errors.append("per-CPU VCD missing pc register dump")

    return len(errors) == 0, errors


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: verify_vcd.py <main.vcd> [per-cpu.vcd ...]")
        return 2

    ok_all = True
    main_vcd = argv[1]
    min_agents, min_pass_sum, min_orch_resets, auto_cpu_vcds = campaign_expectations()
    extra = argv[2:] if len(argv) > 2 else auto_cpu_vcds
    ok, errs = verify_main_vcd(
        main_vcd,
        min_agents=min_agents,
        min_pass_sum=min_pass_sum,
        min_orch_resets=min_orch_resets,
    )
    if ok:
        print(f"[PASS] Main VCD OK: {main_vcd} ({os.path.getsize(main_vcd)} bytes)")
        print(f"       vcd_marker=0xDEADDEAD confirmed")
    else:
        ok_all = False
        print(f"[FAIL] Main VCD: {main_vcd}")
        for e in errs:
            print(f"       - {e}")

    for p in extra:
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