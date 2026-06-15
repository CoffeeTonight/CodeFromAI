"""
Instruction Execution Engine for VerifCPU

Real RV32I subset execution (ALU + Load/Store) + custom dispatch.
Bus transactions go through cpu.bus when attached (key for verification use cases).
"""

from verif_cpu.core.isa import decode, custom_instruction_registry, InstructionType, \
    OPCODE_OP, OPCODE_OP_IMM, OPCODE_CUSTOM0, OPCODE_LOAD, OPCODE_STORE, \
    OPCODE_BRANCH, OPCODE_JAL, OPCODE_JALR, OPCODE_LUI, OPCODE_AUIPC, \
    get_load_store_size, is_load_unsigned
from verif_cpu.utils.xz_sanitize import sanitize_if_xz, dead_value


def _u32(value: int) -> int:
    return value & 0xFFFFFFFF


def _s32(value: int) -> int:
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value & 0x80000000 else value


def _write_rd(cpu, rd: int, value: int):
    """RISC-V x0 is hardwired zero."""
    if rd == 0:
        return
    cpu.regs.write(rd, value)


def _do_bus_read(cpu, address: int, size: int) -> int:
    """Perform bus read. DUMMY_MODE or X/Z contamination → 0xDEADDEAD."""
    width_bits = size * 8
    mask = (1 << width_bits) - 1

    if cpu.state == "DUMMY_MODE":
        return dead_value(width_bits)

    if cpu.bus is None:
        print(f"SCPU{cpu.cpu_id} > bus_read(0x{address:x}, {size}) - NO BUS ATTACHED, returning 0")
        return 0

    txn = cpu.bus.read(address, size)
    if hasattr(cpu, '_record_txn'):
        cpu._record_txn(txn)
    if txn.resp != 0:
        print(f"SCPU{cpu.cpu_id} > bus read error resp={txn.resp} @0x{address:x}")

    xz_mask = getattr(txn, "xz_mask", 0) & mask
    data = sanitize_if_xz(
        cpu, txn.data, xz_mask, width_bits, f"bus_read @0x{address:08x}"
    )
    return data


def _do_bus_write(cpu, address: int, data: int, size: int) -> int:
    """Perform bus write. In DUMMY_MODE still record but do not touch real bus (or do, depending on policy)."""
    if cpu.state == "DUMMY_MODE":
        # Still record the attempted write for replay/diagnosis
        if hasattr(cpu, '_record_txn'):
            from verif_cpu.bus.interface import BusTransaction, BusTransferType
            dummy_txn = BusTransaction(True, address, data, size, BusTransferType.SINGLE, resp=0)
            cpu._record_txn(dummy_txn)
        return 0

    if cpu.bus is None:
        print(f"SCPU{cpu.cpu_id} > bus_write(0x{address:x}, 0x{data:x}, {size}) - NO BUS ATTACHED")
        return 0

    txn = cpu.bus.write(address, data, size)
    if hasattr(cpu, '_record_txn'):
        cpu._record_txn(txn)
    if txn.resp != 0:
        print(f"SCPU{cpu.cpu_id} > bus write error resp={txn.resp} @0x{address:x}")
    return txn.resp


def execute_instruction(cpu, raw_inst: int):
    """
    Execute a single raw instruction (fetch already done).

    Now supports:
    - Full basic RV32I ALU (I+R)
    - LW / SW (and size variants) via attached BusInterface
    - Custom verification instructions
    """
    inst = decode(raw_inst)
    op = inst.opcode

    # --- Custom Verification Instructions ---
    if inst.inst_type == InstructionType.CUSTOM or op == OPCODE_CUSTOM0:
        custom = custom_instruction_registry.get(inst.imm)
        if custom:
            custom.execute(cpu, inst.rd, inst.rs1, inst.rs2, inst.imm)
        else:
            print(f"SCPU{cpu.cpu_id} > Unknown custom selector: 0x{inst.imm:x}")
        return

    # --- RV32I Load (I-type) ---
    if op == OPCODE_LOAD:
        size = get_load_store_size(inst.funct3)
        unsigned = is_load_unsigned(inst.funct3)
        width_bits = size * 8

        if inst.rs1 and cpu.regs.xz_mask(inst.rs1):
            data = sanitize_if_xz(
                cpu, 0, 1, width_bits, f"load rs1 x{inst.rs1} (address X/Z)"
            )
        else:
            base = cpu.regs.read(inst.rs1)
            addr = (base + inst.imm) & ((1 << cpu.bit_width) - 1)
            data = _do_bus_read(cpu, addr, size)

        # Sign or zero extend for smaller loads
        if size < 4:
            mask = (1 << (size * 8)) - 1
            data &= mask
            if not unsigned and (data & (1 << (size*8 - 1))):
                data |= ~mask
        _write_rd(cpu, inst.rd, data)
        return

    # --- RV32I Store (S-type) ---
    if op == OPCODE_STORE:
        base = cpu.read_reg(inst.rs1)
        addr = base + inst.imm
        data = cpu.read_reg(inst.rs2)
        size = get_load_store_size(inst.funct3)
        _do_bus_write(cpu, addr, data, size)
        return

    # --- RV32I LUI / AUIPC ---
    if op == OPCODE_LUI:
        _write_rd(cpu, inst.rd, inst.imm << 12)
        return

    if op == OPCODE_AUIPC:
        _write_rd(cpu, inst.rd, _u32(cpu.pc + (inst.imm << 12)))
        return

    # --- RV32I OP_IMM (I-type ALU) ---
    if op == OPCODE_OP_IMM:
        rs1_val = cpu.read_reg(inst.rs1)
        imm = inst.imm
        shamt = imm & 0x1F
        f3 = inst.funct3
        if f3 == 0x0:      # ADDI
            result = _u32(rs1_val + imm)
        elif f3 == 0x1:    # SLLI
            result = _u32(rs1_val << shamt)
        elif f3 == 0x2:    # SLTI
            result = 1 if _s32(rs1_val) < _s32(imm) else 0
        elif f3 == 0x3:    # SLTIU
            result = 1 if _u32(rs1_val) < _u32(imm) else 0
        elif f3 == 0x7:    # ANDI
            result = rs1_val & imm
        elif f3 == 0x6:    # ORI
            result = rs1_val | imm
        elif f3 == 0x4:    # XORI
            result = rs1_val ^ imm
        elif f3 == 0x5:    # SRLI / SRAI
            if inst.funct7 == 0x20:
                result = _u32(_s32(rs1_val) >> shamt)
            else:
                result = _u32(rs1_val >> shamt)
        else:
            result = rs1_val
        _write_rd(cpu, inst.rd, result)
        return

    # --- RV32I OP (R-type ALU) ---
    if op == OPCODE_OP:
        rs1_val = cpu.read_reg(inst.rs1)
        rs2_val = cpu.read_reg(inst.rs2)
        shamt = rs2_val & 0x1F
        f3 = inst.funct3
        f7 = inst.funct7
        if f3 == 0x0:
            if f7 == 0x20:   # SUB
                result = _u32(rs1_val - rs2_val)
            else:            # ADD
                result = _u32(rs1_val + rs2_val)
        elif f3 == 0x1:      # SLL
            result = _u32(rs1_val << shamt)
        elif f3 == 0x2:      # SLT
            result = 1 if _s32(rs1_val) < _s32(rs2_val) else 0
        elif f3 == 0x3:      # SLTU
            result = 1 if _u32(rs1_val) < _u32(rs2_val) else 0
        elif f3 == 0x7:      # AND
            result = rs1_val & rs2_val
        elif f3 == 0x6:      # OR
            result = rs1_val | rs2_val
        elif f3 == 0x4:      # XOR
            result = rs1_val ^ rs2_val
        elif f3 == 0x5:      # SRL / SRA
            if f7 == 0x20:
                result = _u32(_s32(rs1_val) >> shamt)
            else:
                result = _u32(rs1_val >> shamt)
        else:
            result = rs1_val
        _write_rd(cpu, inst.rd, result)
        return

    # --- RV32I Branch (B-type) ---
    if op == OPCODE_BRANCH:
        rs1_val = cpu.read_reg(inst.rs1)
        rs2_val = cpu.read_reg(inst.rs2)
        f3 = inst.funct3
        take = False
        if f3 == 0x0:    # BEQ
            take = (rs1_val == rs2_val)
        elif f3 == 0x1:  # BNE
            take = (rs1_val != rs2_val)
        elif f3 == 0x4:  # BLT
            take = _s32(rs1_val) < _s32(rs2_val)
        elif f3 == 0x5:  # BGE
            take = _s32(rs1_val) >= _s32(rs2_val)
        elif f3 == 0x6:  # BLTU
            take = _u32(rs1_val) < _u32(rs2_val)
        elif f3 == 0x7:  # BGEU
            take = _u32(rs1_val) >= _u32(rs2_val)

        if take:
            cpu.pc = cpu.pc + inst.imm - 4   # step()에서 +4 할 예정이므로 -4 보정
            return True   # PC already updated
        return False

    # --- RV32I JAL ---
    if op == OPCODE_JAL:
        _write_rd(cpu, inst.rd, cpu.pc + 4)   # return address
        cpu.pc = cpu.pc + inst.imm - 4
        return True

    # --- RV32I JALR ---
    if op == OPCODE_JALR:
        base = cpu.regs.read(inst.rs1)
        target = (base + inst.imm) & ~1       # LSB clear
        _write_rd(cpu, inst.rd, cpu.pc + 4)
        cpu.pc = target - 4
        return True

    # Unknown instruction - do nothing (no PC change)
    return False