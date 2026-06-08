"""Track which RV32I opcodes and custom instructions were executed."""

from verif_cpu.core.isa import InstructionType, OPCODE_CUSTOM0


class InsnCoverageCollector:
    ALL_CUSTOM = {
        0x00: "vstop", 0x01: "vwdt_set", 0x02: "vdummy_on", 0x03: "vdummy_off",
        0x04: "vwdt_pet", 0x10: "vtrace_enter", 0x11: "vtrace_exit", 0x12: "vtrace_log",
        0x13: "vsync", 0x14: "vassert", 0x15: "vforce", 0x16: "vrelease", 0x17: "vwave",
    }

    RV32_NAMES = {
        0x13: "OP_IMM", 0x33: "OP", 0x03: "LOAD", 0x23: "STORE",
        0x63: "BRANCH", 0x6F: "JAL", 0x67: "JALR", 0x37: "LUI",
    }

    def __init__(self):
        self.custom_hits: set[int] = set()
        self.rv32_hits: set[int] = set()

    def record_decode(self, inst):
        if inst.inst_type == InstructionType.CUSTOM or inst.opcode == OPCODE_CUSTOM0:
            self.custom_hits.add(inst.imm)
        elif inst.opcode in self.RV32_NAMES:
            self.rv32_hits.add(inst.opcode)

    def missing_custom(self) -> list[str]:
        return [n for s, n in self.ALL_CUSTOM.items() if s not in self.custom_hits]

    def missing_rv32(self) -> list[str]:
        return [n for op, n in self.RV32_NAMES.items() if op not in self.rv32_hits]

    def all_custom_hit(self) -> bool:
        return len(self.missing_custom()) == 0

    def summary(self) -> dict:
        return {
            "custom": sorted(self.custom_hits),
            "custom_names": [self.ALL_CUSTOM[s] for s in sorted(self.custom_hits)],
            "rv32": sorted(self.rv32_hits),
            "missing_custom": self.missing_custom(),
            "missing_rv32": self.missing_rv32(),
        }