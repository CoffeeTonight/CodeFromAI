"""
Watchdog Timer + Transaction Recorder for VerifCPU

Core of the verification recovery system requested by the user:

- Records bus transactions (for later replay after hang)
- WDT that counts CPU steps (or simulated cycles)
- On timeout: log, optionally reset CPU, replay recent init transactions,
  and selectively put problematic addresses into dummy mode (0xDEAD)

Designed to be attachable to any VerifCPU and observable.
"""

from collections import deque
from dataclasses import dataclass, asdict
from typing import List, Optional, Callable
from verif_cpu.bus.interface import BusTransaction


@dataclass
class RecordedTxn:
    """Lightweight recorded transaction for replay / diagnosis."""
    is_write: bool
    address: int
    data: int
    size: int
    cycle: int = 0          # approximate step count when recorded


class TransactionRecorder:
    """
    Circular buffer of recent bus transactions.
    Used for:
    - Post-hang replay of initialization sequences
    - Debug / bus snooping logs
    """

    def __init__(self, max_records: int = 256):
        self.max_records = max_records
        self._txns: deque[RecordedTxn] = deque(maxlen=max_records)
        self._cycle = 0

    def record(self, txn: BusTransaction, cycle: Optional[int] = None):
        if cycle is None:
            cycle = self._cycle
        rec = RecordedTxn(
            is_write=txn.is_write,
            address=txn.address,
            data=txn.data,
            size=txn.size,
            cycle=cycle
        )
        self._txns.append(rec)
        self._cycle += 1

    def get_recent(self, n: int = 32) -> List[RecordedTxn]:
        """Return the most recent n transactions (oldest first in the slice)."""
        return list(self._txns)[-n:]

    def get_init_sequence(self, max_lookback: int = 64) -> List[RecordedTxn]:
        """Heuristic: return transactions that look like 'init' (writes to low addresses early)."""
        recent = self.get_recent(max_lookback)
        # Simple heuristic: keep early writes or writes to < 0x1000
        return [t for t in recent if t.is_write and (t.address < 0x1000 or t.cycle < 20)]

    # === New powerful query methods (Phase: High-Fidelity Tracing) ===
    def last_write_to(self, address: int, size: int = 4) -> Optional[RecordedTxn]:
        """Return the most recent write that touched the given address (simple overlap check)."""
        for t in reversed(self._txns):
            if t.is_write:
                # simple overlap check
                if t.address <= address < t.address + t.size or address <= t.address < address + size:
                    return t
        return None

    def get_writes_in_range(self, start: int, end: int, max_results: int = 32) -> List[RecordedTxn]:
        """Return recent writes whose address falls inside [start, end)."""
        results = []
        for t in reversed(self._txns):
            if t.is_write and start <= t.address < end:
                results.append(t)
                if len(results) >= max_results:
                    break
        return list(reversed(results))

    def get_reads_to(self, address: int, max_results: int = 16) -> List[RecordedTxn]:
        results = []
        for t in reversed(self._txns):
            if not t.is_write and t.address == address:
                results.append(t)
                if len(results) >= max_results:
                    break
        return list(reversed(results))

    def clear(self):
        self._txns.clear()

    def __len__(self):
        return len(self._txns)


class WatchdogTimer:
    """
    Configurable watchdog.

    - timeout: number of steps/cycles without "pet" before firing
    - auto_recovery: if True, on fire will call the registered recovery callback
    - User spec: 10000 clk default, configurable, log WDT state, console controllable later
    """

    def __init__(self, cpu_id: int, timeout: int = 10000, auto_recovery: bool = True):
        self.cpu_id = cpu_id
        self.timeout = timeout
        self.auto_recovery = auto_recovery
        self.count = 0
        self.enabled = True
        self.fired = False
        self._recovery_cb: Optional[Callable] = None
        self._last_pet_cycle = 0

    def attach_recovery(self, callback: Callable[["WatchdogTimer"], None]):
        """Register what to do on timeout (reset + replay + dummy etc)."""
        self._recovery_cb = callback

    def set_timeout(self, new_timeout: int):
        self.timeout = max(1, new_timeout)
        print(f"SCPU{self.cpu_id} > WDT timeout set to {self.timeout}")

    def pet(self):
        """Reset watchdog counter (firmware or external 'pet' the dog)."""
        self.count = 0
        self.fired = False
        self._last_pet_cycle += 1

    def tick(self, cpu) -> bool:
        """
        Call once per CPU step (or simulated cycle).
        Returns True if the WDT just fired this tick.
        """
        if not self.enabled or self.fired:
            return False

        self.count += 1

        if self.count >= self.timeout:
            self.fired = True
            print(f"SCPU{self.cpu_id} > *** WDT TIMEOUT *** ({self.count} cycles, limit={self.timeout})")
            if self.auto_recovery and self._recovery_cb:
                self._recovery_cb(self, cpu)
            return True
        return False

    def reset(self):
        self.count = 0
        self.fired = False
        self.enabled = True

    def disable(self):
        self.enabled = False

    def enable(self):
        self.enabled = True

    def status(self) -> str:
        return (f"WDT(cpu={self.cpu_id}, enabled={self.enabled}, "
                f"count={self.count}/{self.timeout}, fired={self.fired})")
