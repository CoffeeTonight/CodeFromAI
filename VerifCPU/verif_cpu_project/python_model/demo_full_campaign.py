#!/usr/bin/env python3
"""
Full VerifCPU Campaign — authoritative: iverilog + VCD (make full_campaign).

Python model: verif_cpu.platform.campaign_runner (Verilog-aligned reference).
  python demo_full_campaign.py --py-only     # 26-checklist incl. icode RV32 + VCD gate
  python demo_full_campaign.py --with-model  # iverilog first, then Python cross-check
"""

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verif_cpu.platform.campaign_runner import run_full_campaign

IVERILOG_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "verif_cpu_verilog")
)
VCD_MAIN = os.path.join(IVERILOG_ROOT, "sim_build", "tb_full_campaign.vcd")
LOG_IVL = "/home/user/Desktop/VerifCPU/logs/full_campaign"


def run_iverilog_campaign() -> int:
    """Run iverilog TB + VCD checks — authoritative pass/fail."""
    print("=" * 72)
    print("IVERILOG CAMPAIGN (authoritative) — simulation + VCD verification")
    print("=" * 72)
    os.makedirs(LOG_IVL, exist_ok=True)
    try:
        result = subprocess.run(
            ["make", "full_campaign"],
            cwd=IVERILOG_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        print("[FAIL] make/iverilog not found — install iverilog")
        return 1

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    if result.returncode != 0:
        print("\n[FAIL] iverilog campaign failed (make full_campaign)")
        return result.returncode

    if not os.path.isfile(VCD_MAIN):
        print(f"[FAIL] Main VCD not produced: {VCD_MAIN}")
        return 1

    print("\n" + "=" * 72)
    print("VCD artifacts (open in GTKWave / Surfer):")
    print(f"  Main : {VCD_MAIN}")
    for cid in (1, 2, 3):
        p = os.path.join(LOG_IVL, f"SCPU{cid}.vcd")
        if os.path.isfile(p):
            print(f"  CPU{cid}: {p} ({os.path.getsize(p)} bytes)")
    print("=" * 72)
    print("[SUCCESS] iverilog + VCD verification passed.")
    return 0


def main() -> int:
    with_model = "--model" in sys.argv or "--with-model" in sys.argv
    py_only = "--py-only" in sys.argv

    if py_only:
        return run_full_campaign()

    iv_ok = run_iverilog_campaign()
    if iv_ok != 0:
        return iv_ok

    if with_model:
        print("\n--- Optional Python model cross-check (Verilog-aligned) ---")
        py_ok = run_full_campaign()
        if py_ok != 0:
            print("[WARN] Python model diverged from iverilog PASS — treat iverilog as truth.")
    return 0


if __name__ == "__main__":
    sys.exit(main())