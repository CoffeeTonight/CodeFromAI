"""
High-Fidelity Instruction Tracer for VerifCPU

This module provides rich, structured step-by-step tracing suitable for
serious verification use.

Features:
- Captures register changes (before/after) per instruction
- Records bus effects from the current step
- Structured StepRecord objects (easy to query / post-process)
- Human-readable pretty printing
- Can be enabled per-CPU with low overhead when disabled
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import deque


@dataclass
class RegChange:
    old: int
    new: int


@dataclass
class StepRecord:
    """One executed instruction with rich context."""
    cycle: int
    pc: int
    raw: int
    disasm: str
    reg_changes: Dict[int, RegChange] = field(default_factory=dict)
    # bus_effect: optional future extension (e.g. effective address + data for load/store)
    bus_addr: Optional[int] = None
    bus_data: Optional[int] = None
    bus_is_write: Optional[bool] = None
    bus_size: int = 4


class InstructionTracer:
    """
    Rich per-CPU instruction tracer.

    Usage:
        tracer = InstructionTracer(cpu_id=1, max_steps=1024)
        cpu.attach_instruction_tracer(tracer)

        # during execution
        cpu.step()

        # later
        for rec in tracer.get_last_steps(10):
            print(rec)
    """

    def __init__(self, cpu_id: int, max_steps: int = 2048, enabled: bool = True):
        self.cpu_id = cpu_id
        self.enabled = enabled
        self.max_steps = max_steps
        self._steps: deque[StepRecord] = deque(maxlen=max_steps)
        self._cycle = 0

    def set_enabled(self, enabled: bool):
        self.enabled = enabled

    def record_step(
        self,
        pc: int,
        raw: int,
        disasm: str,
        reg_changes: Dict[int, RegChange],
        bus_addr: Optional[int] = None,
        bus_data: Optional[int] = None,
        bus_is_write: Optional[bool] = None,
        bus_size: int = 4,
    ):
        if not self.enabled:
            return

        rec = StepRecord(
            cycle=self._cycle,
            pc=pc,
            raw=raw,
            disasm=disasm,
            reg_changes=reg_changes,
            bus_addr=bus_addr,
            bus_data=bus_data,
            bus_is_write=bus_is_write,
            bus_size=bus_size,
        )
        self._steps.append(rec)
        self._cycle += 1

    def record_bus_effect(self, addr: int, data: int, is_write: bool, size: int = 4):
        """Record a bus transaction that occurred as part of the current/last step."""
        if not self.enabled or not self._steps:
            return
        last = self._steps[-1]
        last.bus_addr = addr
        last.bus_data = data
        last.bus_is_write = is_write
        last.bus_size = size

    def get_last_steps(self, n: int = 20) -> List[StepRecord]:
        return list(self._steps)[-n:]

    def get_all_steps(self) -> List[StepRecord]:
        return list(self._steps)

    def clear(self):
        self._steps.clear()
        self._cycle = 0

    def __len__(self):
        return len(self._steps)

    def pretty_print_last(self, n: int = 10):
        """Print a nice human-readable trace of the last N steps."""
        steps = self.get_last_steps(n)
        if not steps:
            print(f"[SCPU{self.cpu_id}] No trace steps recorded.")
            return

        print(f"\n=== SCPU{self.cpu_id} Rich Instruction Trace (last {len(steps)} steps) ===")
        for rec in steps:
            changes = []
            for r, ch in sorted(rec.reg_changes.items()):
                changes.append(f"x{r}:{ch.old:08x}->{ch.new:08x}")
            change_str = "  ".join(changes) if changes else "(no reg change)"

            bus_str = ""
            if rec.bus_addr is not None:
                rw = "WR" if rec.bus_is_write else "RD"
                bus_str = f"  [{rw} 0x{rec.bus_addr:08x} = 0x{rec.bus_data:08x}]"

            print(f"[{rec.cycle:04d}] 0x{rec.pc:08x}: {rec.disasm:25s}  {change_str}{bus_str}")
        print("")

    def find_last_write_to_reg(self, reg: int) -> Optional[StepRecord]:
        """Return the most recent step that modified the given register."""
        for rec in reversed(self._steps):
            if reg in rec.reg_changes:
                return rec
        return None

    def get_steps_touching_reg(self, reg: int, max_results: int = 20) -> List[StepRecord]:
        results = []
        for rec in reversed(self._steps):
            if reg in rec.reg_changes:
                results.append(rec)
                if len(results) >= max_results:
                    break
        return list(reversed(results))

    # === Structured Export (for post-processing, coverage, etc.) ===
    def to_dict_list(self) -> list[dict]:
        """Export all recorded steps as a list of dictionaries (structured data)."""
        result = []
        for rec in self._steps:
            step_dict = {
                "cycle": rec.cycle,
                "pc": rec.pc,
                "raw": rec.raw,
                "disasm": rec.disasm,
                "reg_changes": {r: {"old": ch.old, "new": ch.new} for r, ch in rec.reg_changes.items()},
            }
            if rec.bus_addr is not None:
                step_dict["bus"] = {
                    "is_write": rec.bus_is_write,
                    "address": rec.bus_addr,
                    "data": rec.bus_data,
                    "size": rec.bus_size,
                }
            result.append(step_dict)
        return result

    def export_json(self, filepath: str):
        """Export the entire trace to a JSON file."""
        import json
        with open(filepath, "w") as f:
            json.dump(self.to_dict_list(), f, indent=2)
        print(f"[SCPU{self.cpu_id}] Rich trace exported to {filepath}")


# Convenience: snapshot registers for delta computation
def snapshot_regs(cpu, regs_to_watch: List[int] = None) -> Dict[int, int]:
    """Return current values of watched registers (default: x1~x15)."""
    if regs_to_watch is None:
        regs_to_watch = list(range(1, 16))
    return {r: cpu.regs.read(r) for r in regs_to_watch}
