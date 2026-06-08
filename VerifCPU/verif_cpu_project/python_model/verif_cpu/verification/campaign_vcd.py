"""Campaign VCD export + verification — Python analogue of verif_cpu_verilog/tools/verify_vcd.py."""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

DEAD_HEX = 0xDEADDEAD
DEAD_BIN = format(DEAD_HEX, "032b")
DEAD_HEX_MARKERS = ("deaddead",)


def _is_valid_vcd_header(body: str) -> bool:
    return "$enddefinitions" in body and "$scope" in body


def _final_signal_value(body: str, sig_id: str) -> str | None:
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

    with open(path, encoding="utf-8", errors="replace") as f:
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

    m = re.search(r"\$var (?:wire|reg) 32 (\S+) orch_reset_count", body)
    if m:
        rst_val = _final_signal_value(body, m.group(1))
        if rst_val is None or int(rst_val.replace("x", "0").replace("z", "0"), 2) < 4:
            errors.append("orch_reset_count < 4 (missing icode inter-reset / phase resets)")
    else:
        errors.append("VCD missing orch_reset_count")

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
    errors: list[str] = []
    if not os.path.isfile(path):
        return False, [f"missing VCD: {path}"]

    size = os.path.getsize(path)
    if size < 64:
        errors.append(f"VCD too small ({size} bytes): {path}")

    with open(path, encoding="utf-8", errors="replace") as f:
        body = f.read()

    if not _is_valid_vcd_header(body):
        errors.append("not a valid VCD (no $scope / $enddefinitions)")

    if "$scope module TOP" not in body:
        errors.append("per-CPU VCD missing TOP scope")

    if " pc " not in body and "$var reg" not in body:
        errors.append("per-CPU VCD missing pc register dump")

    return len(errors) == 0, errors


def _write_vcd_header(f) -> None:
    f.write("$date\n    " + time.ctime() + "\n$end\n")
    f.write("$version\n    VerifCPU Python Model\n$end\n")
    f.write("$timescale 1ns $end\n\n")


def export_main_campaign_vcd(
    path: Path,
    *,
    vcd_marker: int,
    orch_reset_count: int,
    agent_verify_pass: list[int],
    dead_samples: list[int] | None = None,
) -> None:
    """Write a tb_full_campaign-shaped main VCD for verify_main_vcd()."""
    path.parent.mkdir(parents=True, exist_ok=True)
    dead_samples = dead_samples or [DEAD_HEX]

    with open(path, "w", encoding="utf-8") as f:
        _write_vcd_header(f)
        f.write("$scope module tb_full_campaign $end\n")
        f.write("  $var reg 32 ! vcd_marker $end\n")
        f.write("  $var reg 32 \" orch_reset_count $end\n")
        for i, sid in enumerate(("#", "$", "%")):
            f.write(f"  $var reg 32 {sid} verify_pass $end\n")
        for i, val in enumerate(dead_samples[:3]):
            f.write(f"  $var reg 32 {chr(ord('a') + i)} dead_sample_{i} $end\n")
        f.write("$upscope $end\n")
        f.write("$enddefinitions $end\n\n")
        f.write("#0\n")
        f.write("$dumpvars\n")
        f.write("$end\n\n")
        f.write("#1\n")
        f.write(f"b{format(vcd_marker & 0xFFFFFFFF, '032b')} !\n")
        f.write(f"b{format(orch_reset_count & 0xFFFFFFFF, '032b')} \"\n")
        for sid, val in zip(("#", "$", "%"), agent_verify_pass[:3]):
            f.write(f"b{format(val & 0xFFFFFFFF, '032b')} {sid}\n")
        for i, val in enumerate(dead_samples[:3]):
            f.write(f"b{format(val & 0xFFFFFFFF, '032b')} {chr(ord('a') + i)}\n")


def export_cpu_vcd(path: Path, cpu_id: int, pc: int) -> None:
    """Per-CPU hierarchical export (TOP scope, pc reg) — mirrors wave_export_vcd."""
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_pc = f"pc_{cpu_id}"

    with open(path, "w", encoding="utf-8") as f:
        _write_vcd_header(f)
        f.write("$scope module TOP $end\n")
        f.write(f"  $var reg 32 {safe_pc} pc $end\n")
        f.write("$upscope $end\n")
        f.write("$enddefinitions $end\n\n")
        f.write("#0\n")
        f.write("$dumpvars\n")
        f.write("$end\n\n")
        f.write("#1\n")
        f.write(f"b{format(pc & 0xFFFFFFFF, '032b')} {safe_pc}\n")


def run_vcd_gate(
    main_vcd: Path,
    cpu_vcds: list[Path],
) -> tuple[bool, list[str]]:
    """Run verify_main_vcd + verify_cpu_vcd; return (ok, error_lines)."""
    msgs: list[str] = []
    ok_all = True

    ok, errs = verify_main_vcd(str(main_vcd))
    if ok:
        msgs.append(f"[PASS] Main VCD OK: {main_vcd}")
    else:
        ok_all = False
        msgs.append(f"[FAIL] Main VCD: {main_vcd}")
        msgs.extend(f"       - {e}" for e in errs)

    for p in cpu_vcds:
        ok, errs = verify_cpu_vcd(str(p))
        if ok:
            msgs.append(f"[PASS] CPU VCD OK: {p}")
        else:
            ok_all = False
            msgs.append(f"[FAIL] CPU VCD: {p}")
            msgs.extend(f"       - {e}" for e in errs)

    return ok_all, msgs