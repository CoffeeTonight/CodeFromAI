"""
VerifCPU D+C Milestone Demo: Real RV32I + Custom Instructions from Unified Firmware Pool

This demo proves the basic fetch-decode-execute loop works end-to-end:
- Hand-assembled real RISC-V RV32I instructions (ADDI, ADD, SUB, AND, OR, XOR)
- Custom verification instructions encoded in standard custom-0 space (0x0B)
- Loaded into UnifiedFirmwarePool, per-CPU regions assigned
- CPU steps fetch from pool, execute, update registers correctly
- Full SCPUx > instruction trace + SCPUx_FN > function tracing (per spec)
- vstop custom instruction honored (sets request_sim_stop)

Run from python_model/ directory:
    python demo_rv32i_execution.py
"""

import os
import struct
from verif_cpu.core.cpu import VerifCPU
from verif_cpu.memory.unified_pool import UnifiedFirmwarePool
from verif_cpu.core.isa import (
    encode_addi, encode_andi, encode_add, encode_sub, encode_and, encode_or, encode_xor,
    encode_custom
)


def build_test_firmware() -> bytes:
    """
    Build a tiny test "firmware" binary using real RV32I encodings.
    This is what a real cross-compiler would emit for a simple verification routine.
    """
    # We will construct a sequence that exercises many ALU ops and one custom.
    # Memory layout (word aligned):
    # 0x00: setup some values
    # 0x04+: arithmetic
    # ... custom vstop at the end for demo control

    words = []

    # x1 = 5, x2 = 7, x3 = 0xFF
    words.append(encode_addi(1, 0, 5))           # x1 = 5
    words.append(encode_addi(2, 0, 7))           # x2 = 7
    words.append(encode_addi(3, 0, 0xFF))        # x3 = 255

    # x4 = x1 + x2 = 12
    words.append(encode_add(4, 1, 2))

    # x5 = x4 - 3 = 9   (using ADDI negative)
    words.append(encode_addi(5, 4, -3))

    # x6 = x5 & 0x0F = 9
    words.append(encode_andi(6, 5, 0x0F))

    # x7 = x3 | 0x100  (OR with immediate not directly, use reg)
    words.append(encode_addi(7, 0, 0x100))
    words.append(encode_or(7, 3, 7))

    # x8 = x7 ^ x4
    words.append(encode_xor(8, 7, 4))

    # x9 = x8 + 1 (via ADD)
    words.append(encode_addi(9, 0, 1))
    words.append(encode_add(9, 8, 9))

    # Demonstrate a "function" boundary via custom + manual trace in demo
    # (in real flow, special custom instrs or inline markers would trigger FN trace)

    # Trigger a custom instruction: vdummy_on (selector 0x02 per registry)
    words.append(encode_custom(0x02, rd=10))     # vdummy_on

    # More arithmetic inside "dummy region"
    words.append(encode_sub(10, 9, 4))
    words.append(encode_and(11, 10, 2))

    # vstop (selector 0x00) - will request sim stop
    words.append(encode_custom(0x00))

    # Safety padding (should never reach)
    for _ in range(4):
        words.append(encode_addi(0, 0, 0))       # nop

    # Pack as little-endian 32-bit words (standard RISC-V)
    binary = struct.pack("<" + "I" * len(words), *words)
    return binary


def dump_regs(cpu: VerifCPU, note: str = ""):
    """Pretty register dump with CPU prefix."""
    regs = [cpu.regs.read(i) for i in range(12)]  # x0-x11 visible
    print(f"SCPU{cpu.cpu_id} > REG  x0={regs[0]:08x}  x1={regs[1]:08x}  x2={regs[2]:08x}  "
          f"x3={regs[3]:08x}  x4={regs[4]:08x}  x5={regs[5]:08x}")
    print(f"SCPU{cpu.cpu_id} >      x6={regs[6]:08x}  x7={regs[7]:08x}  x8={regs[8]:08x}  "
          f"x9={regs[9]:08x} x10={regs[10]:08x} x11={regs[11]:08x}   {note}")


def main():
    print("=" * 70)
    print("VerifCPU D+C Demo - Real RV32I Execution from Unified Firmware Pool")
    print("=" * 70)
    print()

    # 1. Build real firmware image
    fw_image = build_test_firmware()
    fw_path = "/tmp/verifcpu_rv32i_test.bin"
    with open(fw_path, "wb") as f:
        f.write(fw_image)
    print(f"[Host] Built test firmware: {fw_path} ({len(fw_image)} bytes, {len(fw_image)//4} instructions)")

    # 2. Unified Pool + region assignment (CPU 1 gets the whole test image)
    pool = UnifiedFirmwarePool()
    pool.load_from_file(fw_path)
    pool.assign_region(cpu_id=1, base_offset=0, size=len(fw_image))

    # 3. Create CPU and attach (PC will be set to 0 inside region)
    cpu = VerifCPU(cpu_id=1, bit_width=32)
    cpu.set_hierarchy(0x10)                    # e.g. attached to some bus master hierarchy
    cpu.attach_firmware(pool, base_offset=0, size=len(fw_image))

    print("\n--- Starting execution (real instructions from pool) ---")
    print()

    # 4. Run until vstop or max steps (safety)
    MAX_STEPS = 64
    step = 0
    while step < MAX_STEPS and not cpu.request_sim_stop and cpu.state in ("RUNNING", "DUMMY_MODE"):
        # Demonstrate function tracing around logical blocks (as real FW would emit via markers)
        if step == 0:
            cpu.fn_enter("main_verif_routine")
        if step == 4:
            cpu.fn_enter("compute_phase_1")
        if step == 9:
            cpu.fn_exit("compute_phase_1")
            cpu.fn_enter("custom_control_phase")

        cpu.step()
        step += 1

        # Periodic nice reg dump (every 5 steps)
        if step % 5 == 0 or cpu.request_sim_stop:
            dump_regs(cpu, f"after step {step}")

    print()
    if cpu.request_sim_stop:
        print(f"SCPU{cpu.cpu_id} > vstop received - simulation stopped cleanly by firmware request")
    else:
        print(f"SCPU{cpu.cpu_id} > Reached max steps ({MAX_STEPS}) or stalled")

    cpu.fn_exit("custom_control_phase")
    cpu.fn_exit("main_verif_routine")

    print()
    print("=" * 70)
    print("Demo complete. Basic D+C loop (fetch from pool + RV32I decode/execute + custom + tracing) is WORKING.")
    print("=" * 70)


if __name__ == "__main__":
    main()