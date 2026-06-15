"""
Simple SoC behavior model — AXI 1:3 address decoder + 3 slave peripherals.

Each slave port has a snoop tap for VerifCPU agents.
"""

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from verif_cpu.bus.interface import BusTransaction, BusTransferType


@dataclass
class SlavePort:
    name: str
    port_id: int
    addr_base: int
    addr_mask: int  # region size = ~mask & base alignment; use size instead
    addr_size: int
    memory: bytearray = field(default_factory=bytearray)
    _snoop_handlers: List[Callable[[BusTransaction, int], None]] = field(default_factory=list)

    def contains(self, addr: int) -> bool:
        return self.addr_base <= addr < self.addr_base + self.addr_size

    def on_snoop(self, handler: Callable[[BusTransaction, int], None]):
        self._snoop_handlers.append(handler)

    def _emit_snoop(self, txn: BusTransaction):
        for h in self._snoop_handlers:
            h(txn, self.port_id)

    # SFR test port: read returns data with X/Z on low byte (for xz_sanitize tests)
    XZ_TEST_OFFSET = 0x0FC

    def read(self, addr: int, size: int) -> BusTransaction:
        off = addr - self.addr_base
        xz_mask = 0
        if self.port_id == 0 and off == self.XZ_TEST_OFFSET:
            data = int.from_bytes(self.memory[off : off + size], "little")
            xz_mask = (1 << (size * 8)) - 1  # all read bits marked X/Z
        else:
            data = int.from_bytes(self.memory[off : off + size], "little")
        txn = BusTransaction(False, addr, data, size, BusTransferType.SINGLE, 0, xz_mask=xz_mask)
        self._emit_snoop(txn)
        return txn

    def write(self, addr: int, data: int, size: int) -> BusTransaction:
        off = addr - self.addr_base
        self.memory[off : off + size] = data.to_bytes(size, "little")
        txn = BusTransaction(True, addr, data, size, BusTransferType.SINGLE, 0)
        self._emit_snoop(txn)
        return txn


@dataclass
class SocInitSequence:
    """SoC boot writes during init (observed by slave VCPUs in Phase A)."""

    steps: List[tuple] = field(default_factory=list)

    @classmethod
    def default_boot(cls):
        try:
            from verif_cpu.soc.soc_init_seq import SOC_INIT_STEPS
            return cls(steps=list(SOC_INIT_STEPS))
        except ImportError:
            return cls(
                steps=[
                    ("write", 0x4000_0000, 0x0000_0001, 4),
                    ("write", 0x4000_0004, 0x0000_00FF, 4),
                    ("write", 0x8000_0000, 0xDEAD_BEEF, 4),
                    ("write", 0x8000_0004, 0xCAFE_BABE, 4),
                    ("write", 0xC000_0000, 0x0000_0080, 4),
                    ("write", 0xC000_0010, 0xDEAD_DEAD, 4),
                ]
            )


class SimpleSoC:
    """
    Minimal SoC: one system bus, 1:3 decoder to SFR / SRAM / UART slaves.
    """

    def __init__(self):
        self.slaves = [
            SlavePort("SFR", 0, 0x4000_0000, 0xFFF00000, 0x1000, bytearray(0x1000)),
            SlavePort("SRAM", 1, 0x8000_0000, 0xFFFF0000, 0x10000, bytearray(0x10000)),
            SlavePort("UART", 2, 0xC000_0000, 0xFFF00000, 0x1000, bytearray(0x1000)),
        ]
        self.init_log: List[BusTransaction] = []

    def _decode(self, addr: int) -> Optional[SlavePort]:
        for s in self.slaves:
            if s.contains(addr):
                return s
        return None

    def bus_read(self, addr: int, size: int = 4) -> BusTransaction:
        slv = self._decode(addr)
        if slv is None:
            return BusTransaction(False, addr, 0xDEAD_DEAD, size, BusTransferType.SINGLE, 1)
        return slv.read(addr, size)

    def bus_write(self, addr: int, data: int, size: int = 4) -> BusTransaction:
        slv = self._decode(addr)
        if slv is None:
            return BusTransaction(True, addr, data, size, BusTransferType.SINGLE, 1)
        return slv.write(addr, data, size)

    def run_init(self, seq: Optional[SocInitSequence] = None):
        if seq is None:
            seq = SocInitSequence.default_boot()
        for step in seq.steps:
            op = step[0]
            if op == "write":
                _, addr, data, size = step
                txn = self.bus_write(addr, data, size)
            else:
                # ("read", addr, expect, size)
                _, addr, expect, size = step[0], step[1], step[2], step[3]
                txn = self.bus_read(addr, size)
                if expect and txn.data != expect:
                    print(
                        f"[SoC] init read mismatch @0x{addr:08x} "
                        f"got=0x{txn.data:08x} expect=0x{expect:08x}"
                    )
            self.init_log.append(txn)

    def attach_snoop(self, port_id: int, handler: Callable[[BusTransaction, int], None]):
        self.slaves[port_id].on_snoop(handler)

    def get_slave(self, name: str) -> SlavePort:
        for s in self.slaves:
            if s.name == name:
                return s
        raise KeyError(name)