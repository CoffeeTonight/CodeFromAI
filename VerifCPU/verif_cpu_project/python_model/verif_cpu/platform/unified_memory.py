"""
Unified memory — shared FW, program store, per-CPU meta (behavior model backing store).
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

CTX_MAGIC = 0x56524643  # "VRFC"
MAX_SLOTS = 32


@dataclass
class VerifSlot:
    bus_addr: int = 0
    icode_ptr: int = 0
    flags: int = 0

    USED = 1
    DONE = 2


@dataclass
class VerifPersistentCtx:
    magic: int = CTX_MAGIC
    phase: int = 0
    slot_count: int = 0
    verify_index: int = 0
    txn_count: int = 0
    init_done: int = 0
    current_addr: int = 0
    slots: List[VerifSlot] = field(default_factory=lambda: [VerifSlot() for _ in range(MAX_SLOTS)])


@dataclass
class UnifiedMemoryLayout:
    """Single file-backed blob with named regions."""

    data: bytearray = field(default_factory=lambda: bytearray(0x0400_0000))
    _ctx_cache: Dict[int, VerifPersistentCtx] = field(default_factory=dict)

    def write_bytes(self, phys: int, blob: bytes):
        end = phys + len(blob)
        if end > len(self.data):
            self.data.extend(b"\x00" * (end - len(self.data)))
        self.data[phys : phys + len(blob)] = blob

    def read_bytes(self, phys: int, size: int) -> bytes:
        return bytes(self.data[phys : phys + size])

    def load_shared_fw(self, base: int, blob: bytes):
        self.write_bytes(base, blob)

    def load_program(self, ptr: int, blob: bytes):
        self.write_bytes(ptr, blob)

    def get_ctx(self, meta_phys: int, cpu_id: int) -> VerifPersistentCtx:
        if cpu_id not in self._ctx_cache:
            self._ctx_cache[cpu_id] = VerifPersistentCtx()
        return self._ctx_cache[cpu_id]

    def ctx_phys(self, meta_base: int) -> int:
        return meta_base + (0x1F000 - 0x1E000)


# Verification program = callable(agent, bus_addr) -> bool
IcodeProgram = Callable


@dataclass
class ProgramStore:
    programs: Dict[int, IcodeProgram] = field(default_factory=dict)
    catalog: List[tuple[str, int]] = field(default_factory=list)

    def register(self, name: str, fn: IcodeProgram) -> int:
        ptr = 0x1000 * (len(self.catalog) + 1)
        self.catalog.append((name, ptr))
        self.programs[ptr] = fn
        return ptr

    def get(self, ptr: int) -> Optional[IcodeProgram]:
        return self.programs.get(ptr)

    def bind_slots(self, ctx: VerifPersistentCtx, ptrs: List[int]):
        for i, ptr in enumerate(ptrs):
            if i >= MAX_SLOTS:
                break
            ctx.slots[i].icode_ptr = ptr