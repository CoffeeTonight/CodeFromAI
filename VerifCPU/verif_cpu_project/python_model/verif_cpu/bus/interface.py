"""
Abstract Bus Interface for VerifCPU

Since the real bus will be controlled via forcing from the simulator,
this interface is designed to be flexible and observable.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


class BusTransferType(Enum):
    SINGLE = auto()
    BURST = auto()
    NARROW = auto()


@dataclass
class BusTransaction:
    is_write: bool
    address: int
    data: int
    size: int          # in bytes
    transfer_type: BusTransferType = BusTransferType.SINGLE
    resp: int = 0      # 0 = OK, non-zero = error
    xz_mask: int = 0   # bits set = X or Z on data (simulation metadata)


class BusInterface(ABC):
    """
    Abstract bus master interface.
    Concrete implementation will be provided depending on the simulation environment
    (pure Python simulation, cocotb, DPI, etc.).
    """

    @abstractmethod
    def read(self, address: int, size: int) -> BusTransaction:
        """Perform a read transaction."""
        pass

    @abstractmethod
    def write(self, address: int, data: int, size: int) -> BusTransaction:
        """Perform a write transaction."""
        pass

    def reset(self):
        """Optional reset behavior for the bus interface."""
        pass
