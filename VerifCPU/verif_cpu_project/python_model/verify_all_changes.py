#!/usr/bin/env python3
"""Self-verification for Claude review fixes (RV32I, sync, custom insn)."""

from __future__ import annotations

import struct
import sys

from verif_cpu.core.cpu import VerifCPU
from verif_cpu.core.execution import execute_instruction, _u32
from verif_cpu.core.isa import (
    OPCODE_OP,
    OPCODE_OP_IMM,
    decode,
    encode_addi,
    encode_auipc,
    encode_custom,
    encode_vassert,
    encode_vforce,
    encode_vrelease,
    encode_vsync,
)
from verif_cpu.core.sync_barrier import SyncBarrier, run_cpus_lockstep, vcpu_sync_mask
from verif_cpu.memory.unified_pool import UnifiedFirmwarePool


def _enc_op_imm(rd, rs1, imm12, funct3, funct7=0):
    imm = imm12 & 0xFFF
    return (
        ((funct7 & 0x7F) << 25)
        | (imm << 20)
        | ((rs1 & 0x1F) << 15)
        | ((funct3 & 7) << 12)
        | ((rd & 0x1F) << 7)
        | OPCODE_OP_IMM
    )


def _enc_op(rd, rs1, rs2, funct3, funct7=0):
    return (
        ((funct7 & 0x7F) << 25)
        | ((rs2 & 0x1F) << 20)
        | ((rs1 & 0x1F) << 15)
        | ((funct3 & 7) << 12)
        | ((rd & 0x1F) << 7)
        | OPCODE_OP
    )


def _enc_branch(rs1, rs2, offset, funct3):
    imm = offset & 0x1FFF
    return (
        (((imm >> 12) & 1) << 31)
        | (((imm >> 5) & 0x3F) << 25)
        | ((rs2 & 0x1F) << 20)
        | ((rs1 & 0x1F) << 15)
        | ((funct3 & 7) << 12)
        | (((imm >> 1) & 0xF) << 8)
        | (((imm >> 11) & 1) << 7)
        | 0x63
    )


class Check:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors: list[str] = []

    def ok(self, name: str, cond: bool, detail: str = ""):
        if cond:
            self.passed += 1
            print(f"  PASS  {name}")
        else:
            self.failed += 1
            msg = f"  FAIL  {name}" + (f" — {detail}" if detail else "")
            print(msg)
            self.errors.append(msg)

    def summary(self) -> int:
        total = self.passed + self.failed
        print(f"\n=== {self.passed}/{total} passed, {self.failed} failed ===")
        return 0 if self.failed == 0 else 1


def test_claude_shift_compare(c: Check):
    """Claude RV32I gap list: slli/srli/srai/slti/sltiu/sll/srl/sra/slt/sltu."""
    print("\n[1] RV32I shift + compare (Claude 10)")
    cpu = VerifCPU(1, 32)
    cpu.trace_enabled = False

    cpu.regs.write(1, 3)
    execute_instruction(cpu, _enc_op_imm(2, 1, 2, funct3=1))
    c.ok("slli x2=x1<<2", cpu.regs.read(2) == 12)

    execute_instruction(cpu, _enc_op_imm(3, 2, 1, funct3=5))
    c.ok("srli x3=x2>>1", cpu.regs.read(3) == 6)

    cpu.regs.write(4, 0xFFFFFFF0)
    execute_instruction(cpu, _enc_op_imm(5, 4, 4, funct3=5, funct7=0x20))
    c.ok("srai sign-extend", _u32(cpu.regs.read(5)) == 0xFFFFFFFF)

    cpu.regs.write(10, 5)
    execute_instruction(cpu, _enc_op_imm(11, 10, 10, funct3=2))
    c.ok("slti 5<10", cpu.regs.read(11) == 1)
    execute_instruction(cpu, _enc_op_imm(11, 10, 3, funct3=2))
    c.ok("slti 5<3 false", cpu.regs.read(11) == 0)

    cpu.regs.write(10, 1)
    execute_instruction(cpu, _enc_op_imm(11, 10, 2, funct3=3))
    c.ok("sltiu 1<2", cpu.regs.read(11) == 1)
    cpu.regs.write(10, 0xFFFFFFFF)
    execute_instruction(cpu, _enc_op_imm(11, 10, 1, funct3=3))
    c.ok("sltiu unsigned 0xFFFFFFFF<1 false", cpu.regs.read(11) == 0)

    cpu.regs.write(12, 0x80000000)
    cpu.regs.write(13, 1)
    execute_instruction(cpu, _enc_op(14, 12, 13, funct3=1))
    c.ok("sll", _u32(cpu.regs.read(14)) == 0)

    cpu.regs.write(12, 12)
    cpu.regs.write(13, 2)
    execute_instruction(cpu, _enc_op(14, 12, 13, funct3=5))
    c.ok("srl", cpu.regs.read(14) == 3)

    cpu.regs.write(12, 0xFFFFFFF0)
    cpu.regs.write(13, 4)
    execute_instruction(cpu, _enc_op(14, 12, 13, funct3=5, funct7=0x20))
    c.ok("sra", _u32(cpu.regs.read(14)) == 0xFFFFFFFF)

    cpu.regs.write(12, 1)
    cpu.regs.write(13, 5)
    execute_instruction(cpu, _enc_op(14, 12, 13, funct3=2))
    c.ok("slt", cpu.regs.read(14) == 1)

    cpu.regs.write(12, 5)
    cpu.regs.write(13, 1)
    execute_instruction(cpu, _enc_op(14, 12, 13, funct3=3))
    c.ok("sltu", cpu.regs.read(14) == 0)

    slt_raw = _enc_op(6, 1, 2, funct3=2)
    sltu_raw = _enc_op(7, 1, 2, funct3=3)
    c.ok("disasm slt", cpu._simple_disasm(decode(slt_raw), slt_raw) == "slt x6,x1,x2")
    c.ok("disasm sltu", cpu._simple_disasm(decode(sltu_raw), sltu_raw) == "sltu x7,x1,x2")


def test_rv32i(c: Check):
    print("\n[2] RV32I (branch, auipc)")
    cpu = VerifCPU(1, 32)
    cpu.trace_enabled = False

    cpu.pc = 0x100
    execute_instruction(cpu, encode_auipc(6, 2))
    c.ok("auipc", cpu.regs.read(6) == 0x100 + 0x2000)

    cpu.pc = 0
    cpu.regs.write(10, 1)
    cpu.regs.write(11, 5)
    execute_instruction(cpu, _enc_branch(10, 11, 16, funct3=4))
    c.ok("blt taken", cpu.pc == 16 - 4)

    cpu.pc = 0
    cpu.regs.write(10, 9)
    cpu.regs.write(11, 5)
    execute_instruction(cpu, _enc_branch(10, 11, 16, funct3=5))
    c.ok("bge taken", cpu.pc == 16 - 4)


def test_custom_insn(c: Check):
    print("\n[3] Custom insn encoding (vforce/vrelease/vassert)")
    cpu = VerifCPU(1, 32)
    cpu.trace_enabled = False

    cpu.regs.write(20, 0)
    cpu.regs.write(21, 0x55)
    execute_instruction(cpu, encode_vforce(20, 21))
    c.ok("vforce rd=target", cpu.forced_regs.get(20) == 0x55)

    execute_instruction(cpu, encode_vrelease(20))
    c.ok("vrelease rd=target", 20 not in cpu.forced_regs)

    cpu.regs.write(1, 0)
    execute_instruction(cpu, encode_vassert(99))
    cov = getattr(cpu, "coverage_collector", None)
    if cov is None:
        from verif_cpu.verification.coverage import attach_coverage
        attach_coverage(cpu)
    execute_instruction(cpu, encode_vassert(99))
    failed_before = sum(r.failed for r in cpu.coverage_collector.assertions.values())
    execute_instruction(cpu, encode_vassert(99))
    failed_after = sum(r.failed for r in cpu.coverage_collector.assertions.values())
    c.ok("vassert_id uses x1 (fail on x1=0)", failed_after > failed_before)

    cpu.regs.write(1, 1)
    passed_before = sum(r.passed for r in cpu.coverage_collector.assertions.values())
    execute_instruction(cpu, encode_vassert(100))
    passed_after = sum(r.passed for r in cpu.coverage_collector.assertions.values())
    c.ok("vassert_id pass on x1=1", passed_after > passed_before)


def test_vsync(c: Check):
    print("\n[4] VSYNC lockstep barrier")
    barrier = SyncBarrier()
    fw = struct.pack(
        "<III",
        encode_addi(1, 0, 1),
        encode_vsync(5),
        encode_custom(0x00),
    )
    cpus = []
    for cid in (1, 2, 3):
        path = f"/tmp/verify_vsync_{cid}.bin"
        with open(path, "wb") as f:
            f.write(fw)
        pool = UnifiedFirmwarePool()
        pool.load_from_file(path)
        pool.assign_region(cid, 0, len(fw))
        cpu = VerifCPU(cid, 32)
        cpu.trace_enabled = False
        cpu.sync_barrier = barrier
        cpu.attach_firmware(pool, 0, len(fw))
        cpus.append(cpu)

    run_cpus_lockstep(
        cpus, max_steps=200, barrier_id=5, barrier_mask=vcpu_sync_mask([1, 2, 3]), barrier=barrier
    )
    c.ok("barrier released", barrier.get_release_count(5) >= 1)
    c.ok("all CPUs past vsync", all(cpu.pc >= 8 for cpu in cpus))
    c.ok("no sync_pending", not any(cpu.sync_pending for cpu in cpus))


def main() -> int:
    print("VerifCPU self-verification")
    c = Check()
    test_claude_shift_compare(c)
    test_rv32i(c)
    test_custom_insn(c)
    test_vsync(c)
    return c.summary()


if __name__ == "__main__":
    sys.exit(main())