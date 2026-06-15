"""
Address changer — translates agent local addresses to unified memory physical offsets.
"""

from enum import IntEnum

from verif_cpu.platform.orchestrator import (
    CTX_LOCAL_BASE,
    META_LOCAL_BASE,
    VerifOrchestrator,
)


class AccessKind(IntEnum):
    SHARED_FW = 0
    META = 1
    PROG = 2


class AddrChanger:
    def __init__(self, orch: VerifOrchestrator):
        self.orch = orch

    def translate(self, cpu_id: int, kind: AccessKind, local_or_ptr: int) -> int:
        if kind == AccessKind.SHARED_FW:
            return self.orch.shared_fw_base + local_or_ptr
        if kind == AccessKind.META:
            if local_or_ptr < META_LOCAL_BASE:
                local_or_ptr = CTX_LOCAL_BASE
            return self.orch.meta_base_for(cpu_id) + (local_or_ptr - META_LOCAL_BASE)
        if kind == AccessKind.PROG:
            return self.orch.prog_store_base + local_or_ptr
        raise ValueError(f"unknown access kind {kind}")