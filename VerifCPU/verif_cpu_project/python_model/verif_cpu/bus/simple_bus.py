"""
Simple In-Memory Bus Interface for early testing and development.

This is NOT the final bus model. It is only for unit testing the CPU core
before connecting to real simulation environments.
"""

from verif_cpu.bus.interface import BusInterface, BusTransaction, BusTransferType


class SimpleMemoryBus(BusInterface):
    """
    Very simple memory bus backed by a Python dictionary.
    Useful for early development and unit tests.
    """

    def __init__(self, memory_size: int = 0x10000):
        self.memory = bytearray(memory_size)
        self.size = memory_size

    def _check_bounds(self, address: int, size: int):
        if address < 0 or address + size > self.size:
            raise ValueError(f"Bus access out of bounds: addr=0x{address:x}, size={size}")

    def read(self, address: int, size: int) -> BusTransaction:
        self._check_bounds(address, size)
        data = int.from_bytes(self.memory[address:address + size], byteorder='little')
        return BusTransaction(
            is_write=False,
            address=address,
            data=data,
            size=size,
            transfer_type=BusTransferType.SINGLE,
            resp=0
        )

    def write(self, address: int, data: int, size: int) -> BusTransaction:
        self._check_bounds(address, size)
        self.memory[address:address + size] = data.to_bytes(size, byteorder='little')
        return BusTransaction(
            is_write=True,
            address=address,
            data=data,
            size=size,
            transfer_type=BusTransferType.SINGLE,
            resp=0
        )

    def load_data(self, address: int, data: bytes):
        """Utility to preload firmware or data."""
        self.memory[address:address + len(data)] = data
