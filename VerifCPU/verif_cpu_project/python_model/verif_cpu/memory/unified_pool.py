"""
Unified Firmware Memory Pool

All VerifCPU instances load their firmware from this single pool.
Each CPU only reads the portion assigned to it.

Supports array (eager) or mmap (lazy, page-on-demand) backing.
"""

from __future__ import annotations

import mmap
import os
from typing import Dict, Optional


class UnifiedFirmwarePool:
    """
    File-backed unified firmware memory.

    - mmap mode: no full-RAM copy; reads fault in only touched pages.
    - eager mode: load_from_file() reads entire image (legacy / small images).
    """

    def __init__(self):
        self._data = bytearray()
        self._mmap: Optional[mmap.mmap] = None
        self._file_path: Optional[str] = None
        self._file_size: int = 0
        self._regions: Dict[int, tuple] = {}   # cpu_id -> (base_offset, size)

    def _close_mmap(self) -> None:
        if self._mmap is not None:
            self._mmap.close()
            self._mmap = None

    def load_from_file(self, filepath: str, *, use_mmap: bool = True) -> None:
        """Attach backing file. Default: mmap (lazy). Pass use_mmap=False to load all."""
        self._close_mmap()
        self._data = bytearray()
        self._file_path = filepath
        self._file_size = os.path.getsize(filepath)

        if use_mmap:
            with open(filepath, "rb") as f:
                self._mmap = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            print(f"[UnifiedPool] mmap backing: {filepath} ({self._file_size} bytes, lazy read)")
        else:
            with open(filepath, "rb") as f:
                self._data = bytearray(f.read())
            print(f"[UnifiedPool] Loaded firmware from {filepath} ({len(self._data)} bytes)")

    def assign_region(self, cpu_id: int, base_offset: int, size: int):
        """Assign a firmware region to a specific CPU."""
        end = base_offset + size
        limit = self._file_size if self._mmap is not None else len(self._data)
        if end > limit:
            raise ValueError(f"Region for CPU{cpu_id} exceeds backing size")
        self._regions[cpu_id] = (base_offset, size)
        print(f"[UnifiedPool] Assigned CPU{cpu_id} region: 0x{base_offset:x} ~ 0x{end - 1:x}")

    def read(self, cpu_id: int, offset: int, size: int) -> bytes:
        """Read from the CPU's assigned region (only touches backing pages needed)."""
        if cpu_id not in self._regions:
            raise ValueError(f"CPU{cpu_id} has no assigned firmware region")

        base, region_size = self._regions[cpu_id]
        if offset + size > region_size:
            raise ValueError(f"CPU{cpu_id} tried to read beyond its firmware region")

        start = base + offset
        if self._mmap is not None:
            return self._mmap[start : start + size]
        return bytes(self._data[start : start + size])

    def get_region(self, cpu_id: int) -> tuple:
        return self._regions.get(cpu_id, (0, 0))