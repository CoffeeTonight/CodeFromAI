"""
VerifAgentCPU — behavior-model verification agent (not cycle-accurate RV32).

Implements Phase A (init log) / Phase B (addr collect) / Phase C (icode dispatch)
with external unified memory + addr changer.
"""

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from verif_cpu.bus.interface import BusTransaction
from verif_cpu.platform.addr_chg import AccessKind, AddrChanger
from verif_cpu.platform.orchestrator import (
    PHASE_A_OFFSET,
    PHASE_B_OFFSET,
    PHASE_C_OFFSET,
    Phase,
    VerifOrchestrator,
)
from verif_cpu.platform.unified_memory import (
    ProgramStore,
    UnifiedMemoryLayout,
    VerifPersistentCtx,
    VerifSlot,
)
from verif_cpu.recovery.wdt import RecordedTxn, TransactionRecorder


@dataclass
class AgentConfig:
    cpu_id: int
    name: str
    role: str  # "master" | "slave"
    tap_port_id: Optional[int] = None  # which SoC decoder port to snoop


class VerifAgentCPU:
    def __init__(
        self,
        cfg: AgentConfig,
        orch: VerifOrchestrator,
        mem: UnifiedMemoryLayout,
        prog_store: ProgramStore,
        addr_chg: AddrChanger,
    ):
        self.cfg = cfg
        self.orch = orch
        self.mem = mem
        self.prog_store = prog_store
        self.addr_chg = addr_chg
        self.phase = Phase.INIT
        self.local_pc = PHASE_A_OFFSET
        self.recorder = TransactionRecorder(max_records=512)
        self.ctx = mem.get_ctx(addr_chg.translate(cfg.cpu_id, AccessKind.META, 0x1F000), cfg.cpu_id)
        self._phase_b_hints: List[int] = []
        self._running = True
        self.verify_pass = 0
        self.verify_fail = 0
        self._snoop_cb: Optional[Callable[[BusTransaction, int], None]] = None
        self.soc_ref = None  # set by tb_dut for icode bus access

    def _log(self, msg: str):
        print(f"SCPU{self.cfg.cpu_id} ({self.cfg.name}) > {msg}")

    def attach_snoop(self, cb: Callable[[BusTransaction, int], None]):
        self._snoop_cb = cb

    def on_bus_txn(self, txn: BusTransaction, port_id: int):
        if self.cfg.role != "slave":
            return
        if self.cfg.tap_port_id is not None and port_id != self.cfg.tap_port_id:
            return
        self.recorder.record(txn)
        if self.phase == Phase.INIT:
            self.ctx.txn_count += 1
        if self.phase == Phase.COLLECT:
            self._phase_b_hints.append(txn.address)

    def soft_reset(self, fw_offset: int, phase: Phase):
        self.local_pc = fw_offset
        self.phase = phase
        self._log(f"soft_reset phase={phase.name} pc=0x{fw_offset:x}")

    # --- Phase runners (shared FW behavior) ---

    def run_phase_a(self, max_events: int = 64):
        self._log(f"Phase A: init logging (tap port {self.cfg.tap_port_id})")
        self.ctx.init_done = 1
        self._log(f"Phase A done: recorded {self.ctx.txn_count} txns on tap")

    def run_phase_b(self):
        self._log("Phase B: collecting verification target addresses")
        self.ctx.slot_count = 0
        seen = set()
        for addr in self._phase_b_hints:
            if addr in seen:
                continue
            seen.add(addr)
            i = self.ctx.slot_count
            self.ctx.slots[i].bus_addr = addr
            self.ctx.slots[i].flags = VerifSlot.USED
            self.ctx.slot_count += 1
            self._log(f"  slot[{i}] bus_addr=0x{addr:08x}")
        self._log(f"Phase B done: {self.ctx.slot_count} unique addresses")

    def run_phase_c_slot(self, slot_index: int):
        """Execute icode for one collected slot (multi-icode + inter-reset flow)."""
        if slot_index >= self.ctx.slot_count:
            return
        self.ctx.verify_index = slot_index
        slot = self.ctx.slots[slot_index]
        self.ctx.current_addr = slot.bus_addr
        prog = self.prog_store.get(slot.icode_ptr)
        name = next((n for n, p in self.prog_store.catalog if p == slot.icode_ptr), "?")
        self._log(
            f"  vexec slot[{slot_index}] "
            f"addr=0x{slot.bus_addr:08x} icode={name} ptr=0x{slot.icode_ptr:x}"
        )
        if prog is None:
            self._log("  FAIL: no program at ptr")
            self.verify_fail += 1
            return
        ok = prog(self, slot.bus_addr)
        if ok:
            slot.flags |= VerifSlot.DONE
            self.verify_pass += 1
            self._log("  PASS")
        else:
            self.verify_fail += 1
            self._log("  FAIL")

    def run_phase_c(self):
        self._log("Phase C: dispatch verification icode")
        for i in range(self.ctx.slot_count):
            self.run_phase_c_slot(i)
        self._log(f"Phase C done: pass={self.verify_pass} fail={self.verify_fail}")

    def run_current_phase(self):
        if self.cfg.role == "master":
            return
        if self.phase == Phase.INIT:
            self.run_phase_a()
        elif self.phase == Phase.COLLECT:
            self.run_phase_b()
        elif self.phase == Phase.VERIFY:
            self.run_phase_c()

    def summary(self) -> dict:
        return {
            "cpu_id": self.cfg.cpu_id,
            "name": self.cfg.name,
            "role": self.cfg.role,
            "phase": self.phase.name,
            "txn_recorded": len(self.recorder),
            "slots": self.ctx.slot_count,
            "verify_pass": self.verify_pass,
            "verify_fail": self.verify_fail,
        }


class MasterAgentCPU:
    """Master agent — mirrors verif_agent_master (Verilog behavior model)."""

    def __init__(
        self,
        cfg: AgentConfig,
        orch: VerifOrchestrator,
        soc_bus,
        *,
        init_done_addr: int = 0,
        init_done_mask: int = 0,
        init_done_value: int = 0,
        poll_max: int = 4096,
    ):
        self.cfg = cfg
        self.orch = orch
        self.soc = soc_bus
        self.init_done_addr = init_done_addr
        self.init_done_mask = init_done_mask
        self.init_done_value = init_done_value
        self.poll_max = poll_max

    def _log(self, msg: str):
        print(f"SCPU{self.cfg.cpu_id} ({self.cfg.name}) > {msg}")

    def init_done_met(self, val: int) -> bool:
        return (val & self.init_done_mask) == self.init_done_value

    def wait_soc_init_done(self) -> bool:
        """Poll INIT_DONE_ADDR until (read & mask) == value — mirrors CAMPAIGN_MASTER_WAIT_INIT_DONE."""
        if self.init_done_addr == 0:
            self._log("init_done poll disabled (ADDR=0)")
            return True
        self._log(
            f"polling init_done @0x{self.init_done_addr:08x} "
            f"mask=0x{self.init_done_mask:08x} value=0x{self.init_done_value:08x}"
        )
        for poll in range(self.poll_max):
            txn = self.soc.bus_read(self.init_done_addr, 4)
            if txn.resp == 0 and self.init_done_met(txn.data):
                self._log(f"init_done met @ poll {poll} (read=0x{txn.data:08x})")
                return True
        self._log(f"init_done TIMEOUT after {self.poll_max} polls")
        return False

    def release_phase(self, phase: Phase, fw_offset: int | None = None):
        self._log(f"phase_release → {phase.name}")
        self.orch.phase_release(phase, fw_offset)

    def inject_verify_addresses(self, addresses: List[int], use_read_hint: bool = True):
        """Broadcast target addresses on SoC bus (hint for slaves)."""
        self._log("injecting verification target addresses onto SoC bus")
        for addr in addresses:
            if use_read_hint:
                self._log(f"  bus_read  0x{addr:08x} (hint, preserves init data)")
                self.soc.bus_read(addr, 4)
            else:
                self._log(f"  bus_write 0x{addr:08x}")
                self.soc.bus_write(addr, 0xFEED_FACE, 4)

    def inject_verify_manifest(self, use_read_hint: bool = True):
        """Inject hints per slave using campaign_manifest.h (Master → slave dispatch)."""
        from verif_cpu.platform.campaign_manifest import all_master_hints

        self._log("injecting per-slave verify targets (campaign_manifest.h)")
        for slave, addr, expect, icode in all_master_hints():
            self._log(
                f"  → slave={slave} addr=0x{addr:08x} expect=0x{expect:08x} icode={icode}"
            )
            if use_read_hint:
                self.soc.bus_read(addr, 4)
            else:
                self.soc.bus_write(addr, 0xFEED_FACE, 4)