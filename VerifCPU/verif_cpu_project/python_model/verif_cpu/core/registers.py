"""
Register File for VerifCPU

Supports configurable bit width (8, 16, 32, 64, 128).
"""

from typing import List


class RegisterFile:
    def __init__(self, bit_width: int = 32, num_regs: int = 32):
        if bit_width not in (8, 16, 32, 64, 128):
            raise ValueError("Unsupported bit width")

        self.bit_width = bit_width
        self.num_regs = num_regs
        self._regs: List[int] = [0] * num_regs
        self._xz_mask: List[int] = [0] * num_regs

        # Mask to keep values within the bit width
        self._mask = (1 << bit_width) - 1

    def read(self, index: int) -> int:
        if not 0 <= index < self.num_regs:
            raise IndexError(f"Register index out of range: {index}")
        return self._regs[index]

    def xz_mask(self, index: int) -> int:
        if not 0 <= index < self.num_regs:
            raise IndexError(f"Register index out of range: {index}")
        return self._xz_mask[index]

    def write(self, index: int, value: int, xz_mask: int = 0):
        if not 0 <= index < self.num_regs:
            raise IndexError(f"Register index out of range: {index}")
        self._regs[index] = value & self._mask
        self._xz_mask[index] = xz_mask & self._mask

    def inject_xz(self, index: int, xz_mask: int):
        """Mark register bits as X/Z without changing stored value."""
        if not 0 <= index < self.num_regs:
            raise IndexError(f"Register index out of range: {index}")
        self._xz_mask[index] = xz_mask & self._mask

    def clear_xz(self, index: int):
        if not 0 <= index < self.num_regs:
            raise IndexError(f"Register index out of range: {index}")
        self._xz_mask[index] = 0

    def reset(self):
        self._regs = [0] * self.num_regs
        self._xz_mask = [0] * self.num_regs

    def __repr__(self):
        return f"RegisterFile(width={self.bit_width}, regs={self._regs})"