"""Global VSYNC barrier — mirrors rtl/verif_cpu_sync.v behavior model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional


def cpu_bit_idx(cpu_id: int) -> int:
    return cpu_id - 1


@dataclass
class SyncBarrier:
    max_cpus: int = 8
    max_sync_ids: int = 32

    expected_mask: Dict[int, int] = field(default_factory=dict)
    arrived_mask: Dict[int, int] = field(default_factory=dict)
    release_count: Dict[int, int] = field(default_factory=dict)
    cpu_waiting: Dict[int, bool] = field(default_factory=dict)
    cpu_wait_id: Dict[int, int] = field(default_factory=dict)
    cpu_go_pulse: Dict[int, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for sync_id in range(self.max_sync_ids):
            self.expected_mask.setdefault(sync_id, 0)
            self.arrived_mask.setdefault(sync_id, 0)
            self.release_count.setdefault(sync_id, 0)
        for idx in range(self.max_cpus):
            self.cpu_waiting.setdefault(idx, False)
            self.cpu_wait_id.setdefault(idx, 0)
            self.cpu_go_pulse.setdefault(idx, False)

    def configure(self, sync_id: int, mask: int) -> None:
        sync_id &= 0xFF
        mask &= (1 << self.max_cpus) - 1
        self.expected_mask[sync_id] = mask
        self.arrived_mask[sync_id] = 0

    def cpu_arrive(self, cpu_id: int, sync_id: int) -> bool:
        sync_id &= 0xFF
        idx = cpu_bit_idx(cpu_id)
        if idx < 0 or idx >= self.max_cpus:
            return False

        self.arrived_mask[sync_id] |= 1 << idx
        self.cpu_waiting[idx] = True
        self.cpu_wait_id[idx] = sync_id

        exp = self.expected_mask[sync_id]
        arr = self.arrived_mask[sync_id]
        if exp != 0 and (arr & exp) == exp:
            self.release_count[sync_id] = self.release_count.get(sync_id, 0) + 1
            for j in range(self.max_cpus):
                if self.cpu_waiting[j] and self.cpu_wait_id[j] == sync_id:
                    self.cpu_go_pulse[j] = True
                    self.cpu_waiting[j] = False
            self.arrived_mask[sync_id] = 0
            return True
        return False

    def cpu_consume_go(self, cpu_id: int) -> bool:
        idx = cpu_bit_idx(cpu_id)
        if idx < 0 or idx >= self.max_cpus:
            return False
        go = self.cpu_go_pulse.get(idx, False)
        if go:
            self.cpu_go_pulse[idx] = False
        return go

    def get_release_count(self, sync_id: int) -> int:
        return self.release_count.get(sync_id & 0xFF, 0)


global_sync_barrier = SyncBarrier()


def vcpu_sync_mask(cpu_ids: list[int]) -> int:
    mask = 0
    for cid in cpu_ids:
        mask |= 1 << (cid - 1)
    return mask


def run_cpus_lockstep(
    cpus: list,
    offset: int = 0,
    max_steps: int = 2000,
    barrier_id: Optional[int] = None,
    barrier_mask: Optional[int] = None,
    barrier: Optional[SyncBarrier] = None,
) -> int:
    hub = barrier or global_sync_barrier
    if barrier_id is not None and barrier_mask is not None:
        hub.configure(barrier_id, barrier_mask)

    for cpu in cpus:
        cpu.pc = offset
        cpu.state = "RUNNING"
        cpu.request_sim_stop = False
        cpu.sync_pending = False
        cpu.sync_hold_pc = False
        if getattr(cpu, "wdt", None):
            cpu.wdt.reset()

    steps = 0
    for step in range(max_steps):
        all_done = True
        for cpu in cpus:
            stopped = cpu.request_sim_stop or getattr(cpu, "sim_stop", False)
            if not stopped:
                all_done = False
                if cpu.state in ("RUNNING", "DUMMY_MODE", "STALLED") or cpu.sync_pending:
                    cpu.step()
        steps = step + 1
        if all_done:
            break
    return steps