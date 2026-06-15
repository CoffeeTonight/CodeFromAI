"""SoC-facing bus adapter — connects VerifCPU to SimpleSoC with per-tap snoop."""

from typing import Callable, List, Optional

from verif_cpu.bus.interface import BusInterface, BusTransaction, BusTransferType
from verif_cpu.soc.simple_soc import SimpleSoC


class SocBusAdapter(BusInterface):
    def __init__(self, soc: SimpleSoC, tap_port_id: Optional[int] = None,
                 snoop_handlers: Optional[List[Callable]] = None):
        self.soc = soc
        self.tap_port_id = tap_port_id
        self._extra_snoop = snoop_handlers or []

    def read(self, address: int, size: int) -> BusTransaction:
        txn = self.soc.bus_read(address, size)
        self._notify(txn)
        return txn

    def write(self, address: int, data: int, size: int) -> BusTransaction:
        txn = self.soc.bus_write(address, data, size)
        self._notify(txn)
        return txn

    def _notify(self, txn: BusTransaction):
        port = self._port_for(txn.address)
        if self.tap_port_id is not None and port != self.tap_port_id:
            return
        for h in self._extra_snoop:
            h(txn, port)

    def _port_for(self, addr: int) -> int:
        if 0x4000_0000 <= addr < 0x4000_1000:
            return 0
        if 0x8000_0000 <= addr < 0x8001_0000:
            return 1
        if 0xC000_0000 <= addr < 0xC000_1000:
            return 2
        return 3