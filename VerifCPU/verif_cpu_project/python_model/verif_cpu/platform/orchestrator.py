"""
VerifOrchestrator — TB-level phase control (behavior model).

Master VCPU drives phase transitions via soft reset + boot_fw_offset broadcast.
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Callable, List, Optional


class Phase(IntEnum):
    INIT = 0
    COLLECT = 1
    VERIFY = 2
    IDLE = 3


# Local firmware map (all agents share this logical layout)
PHASE_A_OFFSET = 0x00000
PHASE_B_OFFSET = 0x04000
PHASE_C_OFFSET = 0x08000
META_LOCAL_BASE = 0x1E000
CTX_LOCAL_BASE = 0x1F000


@dataclass
class VerifOrchestrator:
    shared_fw_base: int = 0x0000_0000
    prog_store_base: int = 0x0100_0000
    meta_base: int = 0x0200_0000
    meta_stride: int = 0x0001_0000

    boot_fw_offset: int = PHASE_A_OFFSET
    phase: Phase = Phase.INIT
    reset_req: bool = False
    reset_count: int = 0

    _reset_handlers: List[Callable[[int, Phase], None]] = field(default_factory=list)

    def meta_base_for(self, cpu_id: int) -> int:
        return self.meta_base + cpu_id * self.meta_stride

    def on_reset(self, handler: Callable[[int, Phase], None]):
        self._reset_handlers.append(handler)

    def phase_release(self, phase: Phase, fw_offset: Optional[int] = None, cpu_mask: int = 0xFFFF):
        if fw_offset is None:
            fw_offset = {
                Phase.INIT: PHASE_A_OFFSET,
                Phase.COLLECT: PHASE_B_OFFSET,
                Phase.VERIFY: PHASE_C_OFFSET,
                Phase.IDLE: PHASE_C_OFFSET,
            }[phase]
        self.phase = phase
        self.boot_fw_offset = fw_offset
        self.reset_req = True
        self.reset_count += 1
        for h in self._reset_handlers:
            h(cpu_mask, phase)
        self.reset_req = False

    def icode_inter_reset(self, cpu_mask: int = 0xFFFF):
        """Pulse soft-reset between consecutive icode slot executions (phase unchanged)."""
        self.reset_count += 1
        for h in self._reset_handlers:
            h(cpu_mask, self.phase)

    def acknowledge_reset(self, cpu_id: int) -> tuple[int, Phase]:
        return self.boot_fw_offset, self.phase