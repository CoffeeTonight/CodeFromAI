"""
VerifCPU Instruction Set Architecture

This module defines the instruction set for VerifCPU.

Base: RISC-V RV32I (simplified for verification modeling)
+ Custom Verification Extension

The focus is on clean extensibility for verification-specific custom instructions.
"""

from enum import Enum, auto
from dataclasses import dataclass
from typing import Callable, Dict, Optional


class InstructionType(Enum):
    """Base RISC-V instruction types (simplified)"""
    R_TYPE = auto()
    I_TYPE = auto()
    S_TYPE = auto()
    B_TYPE = auto()
    U_TYPE = auto()
    J_TYPE = auto()
    CUSTOM = auto()           # For verification custom instructions


@dataclass
class Instruction:
    """Represents a decoded instruction"""
    opcode: int
    rd: int = 0
    rs1: int = 0
    rs2: int = 0
    imm: int = 0
    funct3: int = 0
    funct7: int = 0
    inst_type: InstructionType = InstructionType.R_TYPE
    raw: int = 0


class CustomInstruction:
    """
    Base class for all Custom Verification Instructions.

    Each custom instruction should inherit from this and implement execute().
    """

    def __init__(self, name: str, opcode: int):
        self.name = name
        self.opcode = opcode

    def execute(self, cpu, rd: int, rs1: int, rs2: int, imm: int) -> None:
        """
        Execute the custom instruction.

        Args:
            cpu: Reference to the VerifCPU instance
            rd, rs1, rs2, imm: decoded fields
        """
        raise NotImplementedError


class CustomInstructionRegistry:
    """
    Registry for all custom verification instructions.

    This allows easy registration of new verification-specific instructions
    (vstop, vwdt_set, vdummy_on, vsync, etc.).
    """

    def __init__(self):
        self._instructions: Dict[int, CustomInstruction] = {}

    def register(self, custom_inst: CustomInstruction):
        if custom_inst.opcode in self._instructions:
            raise ValueError(f"Custom instruction opcode 0x{custom_inst.opcode:x} already registered")
        self._instructions[custom_inst.opcode] = custom_inst

    def get(self, opcode: int) -> Optional[CustomInstruction]:
        return self._instructions.get(opcode)

    def is_custom(self, opcode: int) -> bool:
        return opcode in self._instructions


# Global registry instance (can be replaced per CPU instance if needed)
custom_instruction_registry = CustomInstructionRegistry()


# ============================================================
# Example Custom Verification Instructions (to be expanded)
# ============================================================

class VStop(CustomInstruction):
    """Stops simulation (similar to $stop)"""
    def __init__(self):
        super().__init__("vstop", 0x00)

    def execute(self, cpu, rd, rs1, rs2, imm):
        print(f"SCPU{cpu.cpu_id} > vstop executed - Simulation stop requested")
        cpu.request_sim_stop = True


class VWDTSet(CustomInstruction):
    """Set WDT timeout value"""
    def __init__(self):
        super().__init__("vwdt_set", 0x01)

    def execute(self, cpu, rd, rs1, rs2, imm):
        if rs1:
            timeout = cpu.regs.read(rs1)
        elif rd:
            timeout = rd
        else:
            timeout = 10000
        if hasattr(cpu, 'wdt') and cpu.wdt:
            cpu.wdt.set_timeout(timeout)
        print(f"SCPU{cpu.cpu_id} > WDT timeout set to {timeout}")


class VDummyOn(CustomInstruction):
    """Enter dummy data mode"""
    def __init__(self):
        super().__init__("vdummy_on", 0x02)

    def execute(self, cpu, rd, rs1, rs2, imm):
        cpu.enter_dummy_mode()
        print(f"SCPU{cpu.cpu_id} > Entered dummy data mode")


class VDummyOff(CustomInstruction):
    """Exit dummy data mode"""
    def __init__(self):
        super().__init__("vdummy_off", 0x03)

    def execute(self, cpu, rd, rs1, rs2, imm):
        cpu.exit_dummy_mode()
        print(f"SCPU{cpu.cpu_id} > Exited dummy data mode")


class VWDTpet(CustomInstruction):
    """Pet the watchdog (prevent timeout from firmware)"""
    def __init__(self):
        super().__init__("vwdt_pet", 0x04)

    def execute(self, cpu, rd, rs1, rs2, imm):
        if hasattr(cpu, 'wdt') and cpu.wdt:
            cpu.wdt.pet()
        print(f"SCPU{cpu.cpu_id} > WDT petted (count reset)")


# ============================================================
# Advanced Function Tracing Custom Instructions (SCPUx_FN > spec)
# ============================================================

class VTraceEnter(CustomInstruction):
    """Function entry trace marker (emits SCPUx_FN > enter)"""
    def __init__(self):
        super().__init__("vtrace_enter", 0x10)

    def execute(self, cpu, rd, rs1, rs2, imm):
        # imm or rs1에 함수 ID를 넣거나, 간단히 imm를 함수 이름으로 해석 (demo용)
        func_name = f"func_{imm}" if imm else "unknown_func"
        if hasattr(cpu, 'fn_enter'):
            cpu.fn_enter(func_name)
        else:
            print(f"SCPU{cpu.cpu_id}_FN > {func_name} enter")


class VTraceExit(CustomInstruction):
    """Function exit trace marker (emits SCPUx_FN > exit)"""
    def __init__(self):
        super().__init__("vtrace_exit", 0x11)

    def execute(self, cpu, rd, rs1, rs2, imm):
        func_name = f"func_{imm}" if imm else "unknown_func"
        if hasattr(cpu, 'fn_exit'):
            cpu.fn_exit(func_name)
        else:
            print(f"SCPU{cpu.cpu_id}_FN > {func_name} exit")


class VTraceLog(CustomInstruction):
    """Emit a custom trace message with SCPUx > prefix"""
    def __init__(self):
        super().__init__("vtrace_log", 0x12)

    def execute(self, cpu, rd, rs1, rs2, imm):
        msg = f"trace_msg_{imm}" if imm else "trace_point"
        if hasattr(cpu, 'log'):
            cpu.log(f"[Trace] {msg}")
        else:
            print(f"SCPU{cpu.cpu_id} > [Trace] {msg}")


class VSync(CustomInstruction):
    """
    Multi-CPU synchronization point.

    When executed, it emits a clear synchronization marker.
    In future enhancements, this can be connected to a global sync manager
    so that multiple CPUs can wait for each other at specific points.
    """
    def __init__(self):
        super().__init__("vsync", 0x13)

    def execute(self, cpu, rd, rs1, rs2, imm):
        sync_id = imm if imm else (rd if rd else 0)
        msg = f"VSYNC point reached (id={sync_id})"
        if hasattr(cpu, 'log'):
            cpu.log(f"[Sync] {msg}")
        else:
            print(f"SCPU{cpu.cpu_id} > [Sync] {msg}")

        # Future: could increment a shared sync counter or block until other CPUs arrive
        # For now, this is a strong observable barrier for verification.


class VAssert(CustomInstruction):
    """
    Verification assertion.

    If the condition (taken from rs1 or imm) is zero/false, it logs a failure.
    This is extremely useful for self-checking verification firmware.
    """
    def __init__(self):
        super().__init__("vassert", 0x14)

    def execute(self, cpu, rd, rs1, rs2, imm):
        condition = cpu.read_reg(rs1) if rs1 else imm
        passed = bool(condition)

        if passed:
            if hasattr(cpu, 'log'):
                cpu.log(f"[Assert] PASS (id={imm})")
        else:
            msg = f"ASSERTION FAILED (id={imm})"
            if hasattr(cpu, 'log'):
                cpu.log(f"[Assert] {msg}")
            else:
                print(f"SCPU{cpu.cpu_id} > [Assert] {msg}")

        # Feed into coverage collector if present
        if getattr(cpu, 'coverage_collector', None):
            cpu.coverage_collector.record_assert(imm, passed)


class VForce(CustomInstruction):
    """
    Force a register or memory location to a specific value.

    This now actually affects the CPU state in the Python model (powerful for
    verification control and corner-case injection).
    """
    def __init__(self):
        super().__init__("vforce", 0x15)

    def execute(self, cpu, rd, rs1, rs2, imm):
        # Convention: rs1 = target (reg index or addr), rs2 or rd/imm = value
        target = cpu.read_reg(rs1) if rs1 else imm
        value = cpu.read_reg(rs2) if rs2 else (rd if rd else imm)

        # Simple heuristic: small values are likely registers, large are memory
        if 0 <= target < 32:
            cpu.force_reg(target, value)
        else:
            cpu.force_mem(target, value)


class VRelease(CustomInstruction):
    """
    Release a previously forced register or memory location.
    """
    def __init__(self):
        super().__init__("vrelease", 0x16)

    def execute(self, cpu, rd, rs1, rs2, imm):
        target = cpu.read_reg(rs1) if rs1 else imm

        if 0 <= target < 32:
            cpu.release_reg(target)
        else:
            cpu.release_mem(target)


class VWave(CustomInstruction):
    """
    Firmware-controlled waveform dump command.

    This instruction allows firmware to directly control waveform dumping,
    similar to how $dumpfile / $dumpon / $dumpoff work in simulation.

    Common usage from firmware:
    - vwave 1     → Start dumping
    - vwave 0     → Stop dumping
    - vwave 2, id → Dump specific scope or with ID
    """
    def __init__(self):
        super().__init__("vwave", 0x17)

    def execute(self, cpu, rd, rs1, rs2, imm):
        cmd = rd if rd else imm
        arg = rs1 if rs1 else 0

        if hasattr(cpu, 'wave_dumper') and cpu.wave_dumper:
            cpu.wave_dumper.handle_command(cmd, arg)
        else:
            action = {0: "OFF", 1: "ON", 2: "DUMP_ALL", 3: "DUMP_SCOPE"}.get(cmd, f"CMD_{cmd}")
            if hasattr(cpu, 'log'):
                cpu.log(f"[Wave] Wave dump command: {action} (arg={arg})")
            else:
                print(f"SCPU{cpu.cpu_id} > [Wave] {action} (arg={arg})")


# Register default custom instructions
custom_instruction_registry.register(VStop())
custom_instruction_registry.register(VWDTSet())
custom_instruction_registry.register(VDummyOn())
custom_instruction_registry.register(VDummyOff())
custom_instruction_registry.register(VWDTpet())
custom_instruction_registry.register(VTraceEnter())
custom_instruction_registry.register(VTraceExit())
custom_instruction_registry.register(VTraceLog())
custom_instruction_registry.register(VSync())
custom_instruction_registry.register(VAssert())
custom_instruction_registry.register(VForce())
custom_instruction_registry.register(VRelease())
custom_instruction_registry.register(VWave())


# ============================================================
# RISC-V RV32I opcode constants (subset for VerifCPU D+C phase)
# ============================================================
OPCODE_LOAD     = 0x03  # 0000011
OPCODE_STORE    = 0x23  # 0100011
OPCODE_BRANCH   = 0x63  # 1100011
OPCODE_JALR     = 0x67  # 1100111
OPCODE_JAL      = 0x6F  # 1101111
OPCODE_OP_IMM   = 0x13  # 0010011  (ADDI, ANDI, ORI, XORI, SLLI etc)
OPCODE_OP       = 0x33  # 0110011  (ADD, SUB, AND, OR, XOR, SLL, SRL, SRA)
OPCODE_LUI      = 0x37  # 0110111
OPCODE_AUIPC    = 0x17  # 0010111
OPCODE_CUSTOM0  = 0x0B  # 0001011  -- Recommended RISC-V custom-0 space for verification instrs


def decode(raw_inst: int) -> Instruction:
    """
    RV32I decoder focused on ALU (I-type + R-type) + custom verification extension.
    Sign-extension and field extraction follow RISC-V spec.
    """
    opcode = raw_inst & 0x7F
    rd = (raw_inst >> 7) & 0x1F
    funct3 = (raw_inst >> 12) & 0x7
    rs1 = (raw_inst >> 15) & 0x1F
    rs2 = (raw_inst >> 20) & 0x1F
    funct7 = (raw_inst >> 25) & 0x7F

    inst_type = InstructionType.I_TYPE
    imm = 0

    if opcode == OPCODE_OP:  # R-type ALU
        inst_type = InstructionType.R_TYPE
        # imm not used; funct7/funct3 decide ADD vs SUB etc.
    elif opcode == OPCODE_OP_IMM:  # I-type ALU
        inst_type = InstructionType.I_TYPE
        imm = (raw_inst >> 20) & 0xFFF
        if imm & 0x800:
            imm |= ~0xFFF   # sign-extend 12-bit
    elif opcode == OPCODE_CUSTOM0:
        inst_type = InstructionType.CUSTOM
        # Our convention for custom verification instructions in this model:
        # Use funct7 (7 bits) as the custom selector (0x00=vstop, 0x01=vwdt_set, ...)
        # This keeps binary layout realistic while registry stays simple.
        imm = funct7          # repurpose: custom selector lives in funct7 for our custom instrs
    elif opcode in (OPCODE_LUI, OPCODE_AUIPC):
        inst_type = InstructionType.U_TYPE
        imm = (raw_inst >> 12) & 0xFFFFF
    elif opcode == OPCODE_JAL:
        inst_type = InstructionType.J_TYPE
        imm = ((raw_inst >> 31) & 0x1) << 20
        imm |= ((raw_inst >> 21) & 0x3FF) << 1
        imm |= ((raw_inst >> 20) & 0x1) << 11
        imm |= ((raw_inst >> 12) & 0xFF) << 12
        if imm & (1 << 20):
            imm |= ~((1 << 21) - 1)
    else:
        # For other opcodes we still decode fields so later instrs (load/store/branch) work
        if opcode in (OPCODE_LOAD, OPCODE_JALR):
            inst_type = InstructionType.I_TYPE
            imm = (raw_inst >> 20) & 0xFFF
            if imm & 0x800:
                imm |= ~0xFFF
        elif opcode == OPCODE_STORE:
            inst_type = InstructionType.S_TYPE
            imm = ((raw_inst >> 25) << 5) | ((raw_inst >> 7) & 0x1F)
            if imm & 0x800:
                imm |= ~0xFFF
        elif opcode == OPCODE_BRANCH:
            inst_type = InstructionType.B_TYPE
            imm = (((raw_inst >> 31) & 0x1) << 12) | (((raw_inst >> 25) & 0x3F) << 5) | \
                  (((raw_inst >> 8) & 0xF) << 1) | ((raw_inst >> 7) & 0x1)
            if imm & (1 << 12):
                imm |= ~((1 << 13) - 1)
        else:
            inst_type = InstructionType.I_TYPE  # safe default
            imm = (raw_inst >> 20) & 0xFFF
            if imm & 0x800:
                imm |= ~0xFFF

    return Instruction(
        opcode=opcode,
        rd=rd,
        rs1=rs1,
        rs2=rs2,
        imm=imm,
        funct3=funct3,
        funct7=funct7,
        inst_type=inst_type,
        raw=raw_inst
    )


# ============================================================
# Simple RV32I + Custom instruction encoder (for building test firmware in demos)
# ============================================================

def encode_r_type(rd: int, rs1: int, rs2: int, funct3: int, funct7: int = 0) -> int:
    """Encode R-type (OP) instruction."""
    return ((funct7 & 0x7F) << 25) | ((rs2 & 0x1F) << 20) | ((rs1 & 0x1F) << 15) | \
           ((funct3 & 0x7) << 12) | ((rd & 0x1F) << 7) | OPCODE_OP

def encode_i_type(opcode: int, rd: int, rs1: int, imm: int, funct3: int = 0) -> int:
    """Encode I-type instruction (OP_IMM, LOAD, JALR, CUSTOM with our convention)."""
    imm12 = imm & 0xFFF
    return (imm12 << 20) | ((rs1 & 0x1F) << 15) | ((funct3 & 0x7) << 12) | ((rd & 0x1F) << 7) | (opcode & 0x7F)

def encode_custom(custom_sel: int, rd: int = 0, rs1: int = 0, rs2: int = 0) -> int:
    """
    Encode one of our verification custom instructions in custom-0 space.
    custom_sel goes into funct7 per our decode convention (keeps it realistic).
    """
    # funct7 = custom_sel, funct3=0, rs2 unused for most v* instr
    return ((custom_sel & 0x7F) << 25) | ((rs2 & 0x1F) << 20) | ((rs1 & 0x1F) << 15) | \
           (0 << 12) | ((rd & 0x1F) << 7) | OPCODE_CUSTOM0


# Common ALU immediates
def encode_addi(rd: int, rs1: int, imm: int) -> int:
    return encode_i_type(OPCODE_OP_IMM, rd, rs1, imm, funct3=0x0)

def encode_andi(rd: int, rs1: int, imm: int) -> int:
    return encode_i_type(OPCODE_OP_IMM, rd, rs1, imm, funct3=0x7)

def encode_ori(rd: int, rs1: int, imm: int) -> int:
    return encode_i_type(OPCODE_OP_IMM, rd, rs1, imm, funct3=0x6)

def encode_add(rd: int, rs1: int, rs2: int) -> int:
    return encode_r_type(rd, rs1, rs2, funct3=0x0, funct7=0x00)

def encode_sub(rd: int, rs1: int, rs2: int) -> int:
    return encode_r_type(rd, rs1, rs2, funct3=0x0, funct7=0x20)

def encode_and(rd: int, rs1: int, rs2: int) -> int:
    return encode_r_type(rd, rs1, rs2, funct3=0x7, funct7=0x00)

def encode_or(rd: int, rs1: int, rs2: int) -> int:
    return encode_r_type(rd, rs1, rs2, funct3=0x6, funct7=0x00)

def encode_xor(rd: int, rs1: int, rs2: int) -> int:
    return encode_r_type(rd, rs1, rs2, funct3=0x4, funct7=0x00)


# --- Load / Store encoders (RV32I) ---
def encode_lw(rd: int, rs1: int, imm: int) -> int:
    return encode_i_type(OPCODE_LOAD, rd, rs1, imm, funct3=0x2)   # LW = funct3 010

def encode_sw(rs2: int, rs1: int, imm: int) -> int:
    # S-type: imm split across [31:25] and [11:7]
    imm12 = imm & 0xFFF
    imm_high = (imm12 >> 5) & 0x7F
    imm_low = imm12 & 0x1F
    return ((imm_high & 0x7F) << 25) | ((rs2 & 0x1F) << 20) | ((rs1 & 0x1F) << 15) | \
           (0x2 << 12) | ((imm_low & 0x1F) << 7) | OPCODE_STORE


# --- Advanced Tracing Custom Instruction encoders (for demo firmware) ---
def encode_vtrace_enter(func_id: int = 0) -> int:
    """Emit vtrace_enter (selector 0x10). func_id is passed in rd field for simplicity."""
    return encode_custom(0x10, rd=func_id)

def encode_vtrace_exit(func_id: int = 0) -> int:
    """Emit vtrace_exit (selector 0x11)"""
    return encode_custom(0x11, rd=func_id)

def encode_vtrace_log(msg_id: int = 0) -> int:
    """Emit vtrace_log (selector 0x12)"""
    return encode_custom(0x12, rd=msg_id)


def encode_vsync(sync_id: int = 0) -> int:
    """Emit vsync synchronization point (selector 0x13)"""
    return encode_custom(0x13, rd=sync_id)


def encode_vassert(assert_id: int = 0) -> int:
    """Emit vassert (selector 0x14)"""
    return encode_custom(0x14, rd=assert_id)


def encode_vforce(addr_reg: int = 0, data_reg: int = 0) -> int:
    """Emit vforce request (selector 0x15)"""
    return encode_custom(0x15, rd=addr_reg, rs2=data_reg)


def encode_vrelease(addr_reg: int = 0) -> int:
    """Emit vrelease request (selector 0x16)"""
    return encode_custom(0x16, rd=addr_reg)


# --- Waveform Dump Control ---
def encode_lui(rd: int, imm20: int) -> int:
    """LUI rd, imm20"""
    return ((imm20 & 0xFFFFF) << 12) | ((rd & 0x1F) << 7) | OPCODE_LUI


def encode_vstop() -> int:
    return encode_custom(0x00)


def encode_vwdt_set(timeout_imm: int = 0, rs1: int = 0) -> int:
    """Pass timeout via rs1 register (preferred) or rd field as immediate carrier."""
    if rs1:
        return encode_custom(0x01, rs1=rs1)
    return encode_custom(0x01, rd=timeout_imm)


def encode_vdummy_on() -> int:
    return encode_custom(0x02)


def encode_vdummy_off() -> int:
    return encode_custom(0x03)


def encode_vwdt_pet() -> int:
    return encode_custom(0x04)


def encode_vwave(cmd: int = 0, arg: int = 0) -> int:
    """
    Emit vwave command for firmware-controlled waveform dumping.
    cmd: 0=OFF, 1=ON, 2=ALL, etc.
    """
    return encode_custom(0x17, rd=cmd, rs1=arg)


# --- Branch / Jump encoders (basic) ---
def encode_beq(rs1: int, rs2: int, imm: int) -> int:
    """BEQ rs1, rs2, imm"""
    imm12 = imm & 0xFFF
    imm_high = (imm12 >> 5) & 0x7F
    imm_low = imm12 & 0x1F
    return ((imm_high & 0x7F) << 25) | ((rs2 & 0x1F) << 20) | ((rs1 & 0x1F) << 15) | \
           (0x0 << 12) | ((imm_low & 0x1F) << 7) | OPCODE_BRANCH

def encode_jal(rd: int, imm: int) -> int:
    """JAL rd, imm — byte offset relative to current PC (signed, 21-bit)."""
    imm21 = imm & 0x1FFFFF
    if imm21 & (1 << 20):
        imm21 -= 1 << 21
    b20 = (imm21 >> 20) & 0x1
    b10_1 = (imm21 >> 1) & 0x3FF
    b11 = (imm21 >> 11) & 0x1
    b19_12 = (imm21 >> 12) & 0xFF
    enc = (b20 << 31) | (b10_1 << 21) | (b11 << 20) | (b19_12 << 12)
    return enc | ((rd & 0x1F) << 7) | OPCODE_JAL

def encode_jalr(rd: int, rs1: int, imm: int) -> int:
    """JALR rd, rs1, imm"""
    imm12 = imm & 0xFFF
    return (imm12 << 20) | ((rs1 & 0x1F) << 15) | (0 << 12) | ((rd & 0x1F) << 7) | OPCODE_JALR


def get_load_store_size(funct3: int) -> int:
    """Return byte size for load/store from funct3."""
    if funct3 in (0x0, 0x4): return 1      # LB / LBU
    if funct3 in (0x1, 0x5): return 2      # LH / LHU
    if funct3 == 0x2:        return 4      # LW
    return 4


def is_load_unsigned(funct3: int) -> bool:
    return funct3 in (0x4, 0x5, 0x6)   # LBU, LHU, LWU (future)