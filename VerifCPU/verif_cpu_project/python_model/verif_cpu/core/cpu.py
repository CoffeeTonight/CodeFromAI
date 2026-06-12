"""
VerifCPU Core - Pure Python Implementation (Work in Progress)

This is the central class for the verification-specialized CPU.
It is designed to be highly observable and controllable from Python.
"""

from typing import Optional

from verif_cpu.core.registers import RegisterFile
from verif_cpu.core.isa import decode, custom_instruction_registry, InstructionType
from verif_cpu.core import execution as exec_engine
from verif_cpu.bus.interface import BusInterface
from verif_cpu.memory.unified_pool import UnifiedFirmwarePool
from verif_cpu.tracing.tracer import FunctionTracer
from verif_cpu.tracing.instruction_tracer import InstructionTracer, snapshot_regs, RegChange
from verif_cpu.tracing.wave_dumper import WaveDumper
from verif_cpu.recovery.wdt import WatchdogTimer, TransactionRecorder


class CPUState:
    RUNNING = "RUNNING"
    STALLED = "STALLED"
    RESET = "RESET"
    DUMMY_MODE = "DUMMY_MODE"


class VerifCPU:
    def __init__(self, cpu_id: int, bit_width: int = 32, bus: Optional[BusInterface] = None):
        if bit_width not in (8, 16, 32, 64, 128):
            raise ValueError(f"Unsupported bit width: {bit_width}")

        self.cpu_id = cpu_id
        self.bit_width = bit_width
        self.state = CPUState.RUNNING
        self.pc = 0

        self.regs = RegisterFile(bit_width=bit_width)
        self.bus = bus

        self.hierarchy_id: Optional[int] = None
        self.trace_enabled = True
        self.verbose_trace = False   # True면 step마다 주요 레지스터 변화 출력

        # Firmware memory (from Unified Pool)
        self.firmware: Optional[UnifiedFirmwarePool] = None
        self.firmware_base: int = 0
        self.firmware_size: int = 0

        # Used by custom instructions (e.g. vstop)
        self.request_sim_stop = False

        # Function tracer (SCPUx_FN > prefix per spec)
        self.tracer = FunctionTracer(cpu_id, enabled=True)

        # Recovery / WDT infrastructure (user spec: hang detection + replay + dummy)
        self.recorder: Optional[TransactionRecorder] = None
        self.wdt: Optional[WatchdogTimer] = None
        self._problem_addrs: set = set()   # addresses that caused issues → dummy

        # High-fidelity instruction tracer (new powerful observability feature)
        self.instr_tracer: Optional[InstructionTracer] = None
        self._trace_regs = list(range(1, 16))  # default registers to track for deltas

        # Dedicated log file (user spec: all CPU activity to separate file)
        self.log_file = None   # can be set to open file handle later

        # Force/Release mechanism (powerful verification control)
        self.forced_regs: dict[int, int] = {}
        self.forced_mem: dict[int, int] = {}
        self.force_active = True

        # Coverage & Assertion collection
        self.coverage_collector = None

        # Waveform dumper (firmware-controlled wave dump)
        self.wave_dumper: Optional[WaveDumper] = None

        # === Verification Metrics (for reporting / campaign analysis) ===
        self.total_steps = 0
        self.recovery_count = 0
        self.last_pc = 0
        self.xz_warn_count = 0

    def set_hierarchy(self, hierarchy_id: int):
        self.hierarchy_id = hierarchy_id
        if self.trace_enabled:
            print(f"SCPU{self.cpu_id} > Hierarchy set to 0x{hierarchy_id:x}")

    def attach_firmware(self, pool: UnifiedFirmwarePool, base_offset: int, size: int):
        """Connect this CPU to its firmware region in the Unified Pool.
        PC is reset to 0 (start of the assigned region).
        """
        self.firmware = pool
        self.firmware_base = base_offset
        self.firmware_size = size
        self.pc = 0
        if self.trace_enabled:
            print(f"SCPU{self.cpu_id} > Firmware attached: offset=0x{base_offset:x}, size={size}")

    def stall(self):
        if self.state == CPUState.RUNNING:
            self.state = CPUState.STALLED
            if self.trace_enabled:
                print(f"SCPU{self.cpu_id} > Stalled")

    def resume(self):
        if self.state == CPUState.STALLED:
            self.state = CPUState.RUNNING
            if self.trace_enabled:
                print(f"SCPU{self.cpu_id} > Resumed")

    def enter_dummy_mode(self):
        self.state = CPUState.DUMMY_MODE
        if self.trace_enabled:
            print(f"SCPU{self.cpu_id} > Entered DUMMY_MODE")

    def exit_dummy_mode(self):
        if self.state == CPUState.DUMMY_MODE:
            self.state = CPUState.RUNNING
            if self.trace_enabled:
                print(f"SCPU{self.cpu_id} > Exited DUMMY_MODE")

    def reset(self, replay_transactions: bool = True):
        """
        Reset the CPU.
        If replay_transactions=True and a recorder exists, it will first replay
        all previously recorded bus transactions (snooped init sequence) before
        continuing with its own firmware. This is a key verification feature for
        fast bring-up after hang/reset.
        """
        self.state = CPUState.RESET
        self.pc = 0
        self.regs.reset()
        self.request_sim_stop = False

        if hasattr(self, 'tracer'):
            self.tracer.reset()

        if self.trace_enabled:
            print(f"SCPU{self.cpu_id} > Reset")

        # Replay recorded transactions (bus snooping replay)
        if replay_transactions and self.recorder and len(self.recorder) > 0:
            self._replay_recorded_transactions()

    def step(self):
        """Fetch + Decode + Execute one instruction from attached firmware.
        PC is always region-relative (0 = start of assigned firmware region).
        """
        if self.state not in (CPUState.RUNNING, CPUState.DUMMY_MODE):
            return

        self.total_steps += 1
        self.last_pc = self.pc

        # --- Fetch (PC is offset within the CPU's firmware region) ---
        if self.firmware is None:
            # Early development mode: infinite NOPs (ADDI x0,x0,0)
            raw_inst = 0x00000013
            if self.trace_enabled:
                print(f"SCPU{self.cpu_id} > 0x{self.pc:08x}: nop (no firmware)")
        else:
            try:
                # Correct: use self.pc directly as region offset (not subtracting base)
                raw_bytes = self.firmware.read(self.cpu_id, self.pc, 4)
                raw_inst = int.from_bytes(raw_bytes, byteorder='little')
            except Exception as e:
                print(f"SCPU{self.cpu_id} > Firmware read error at pc=0x{self.pc:x}: {e}")
                self.state = CPUState.STALLED
                return

        # --- Decode & Execute (real work happens in execution dispatch) ---
        inst = decode(raw_inst)
        if getattr(self, "insn_coverage", None):
            self.insn_coverage.record_decode(inst)
        disasm = self._simple_disasm(inst, raw_inst)

        # High-fidelity tracing snapshot (always safe)
        before_regs = snapshot_regs(self, getattr(self, '_trace_regs', list(range(1, 16))))

        pc_already_updated = False

        if inst.inst_type == InstructionType.CUSTOM:
            custom = custom_instruction_registry.get(inst.imm)
            if custom:
                if self.trace_enabled:
                    print(f"SCPU{self.cpu_id} > 0x{self.pc:08x}: {custom.name} (custom)")
                custom.execute(self, inst.rd, inst.rs1, inst.rs2, inst.imm)
            else:
                print(f"SCPU{self.cpu_id} > Unknown custom selector: 0x{inst.imm:x} at 0x{self.pc:08x}")
            self.pc += 4
        else:
            if self.trace_enabled:
                print(f"SCPU{self.cpu_id} > 0x{self.pc:08x}: {disasm}")
            pc_already_updated = exec_engine.execute_instruction(self, raw_inst)

            if self.state in (CPUState.RUNNING, CPUState.DUMMY_MODE) and not pc_already_updated:
                self.pc += 4

        # High-fidelity tracing hook (for external rich tracers)
        if getattr(self, '_trace_step_callback', None):
            try:
                after_regs = snapshot_regs(self, self._trace_regs)
                reg_changes = {}
                for r in self._trace_regs:
                    oldv = before_regs.get(r, 0)
                    newv = after_regs.get(r, 0)
                    if oldv != newv:
                        reg_changes[r] = RegChange(oldv, newv)
                self._trace_step_callback(
                    pc=self.pc,
                    raw=raw_inst,
                    disasm=disasm,
                    reg_changes=reg_changes
                )
            except Exception as e:
                print(f"SCPU{self.cpu_id} > trace callback error: {e}")

            # Attach most recent bus transaction to the rich trace (if recorder exists)
            if self.instr_tracer and self.recorder and len(self.recorder) > 0:
                try:
                    last_txn = self.recorder.get_recent(1)[0]
                    self.instr_tracer.record_bus_effect(
                        addr=last_txn.address,
                        data=last_txn.data,
                        is_write=last_txn.is_write,
                        size=last_txn.size
                    )
                except Exception:
                    pass

        # Feed PC to coverage collector (basic instruction coverage)
        if self.coverage_collector:
            self.coverage_collector.record_pc(self.pc)

        # Waveform dumping - record key signals with hierarchy awareness
        if self.wave_dumper and self.wave_dumper.enabled:
            self.wave_dumper.tick(self.pc)

            # Use hierarchy_id to create a scope (e.g. "CPU1" or "Master_AHB0")
            scope = f"CPU{self.cpu_id}"
            if self.hierarchy_id is not None:
                scope = f"Hier{self.hierarchy_id:02x}"

            self.wave_dumper.record_change("pc", self.pc, scope=scope)

            for r in [1, 2, 3]:
                val = self.read_reg(r)
                self.wave_dumper.record_change(f"x{r}", val, scope=scope)

        # --- WDT tick (hang detection) ---
        self.wdt_tick()

        # --- Verbose trace (optional) ---
        if self.verbose_trace and self.trace_enabled:
            r = [self.regs.read(i) for i in range(6)]
            self._log(f"  regs: x1={r[1]:08x} x2={r[2]:08x} x3={r[3]:08x} x4={r[4]:08x} x5={r[5]:08x}")

    def _simple_disasm(self, inst, raw: int) -> str:
        """Very basic disassembly for trace readability during early D+C phase."""
        op = inst.opcode
        if op == 0x13:  # OP_IMM
            f3 = inst.funct3
            if f3 == 0: return f"addi x{inst.rd},x{inst.rs1},{inst.imm}"
            if f3 == 7: return f"andi x{inst.rd},x{inst.rs1},0x{inst.imm:x}"
            if f3 == 6: return f"ori x{inst.rd},x{inst.rs1},0x{inst.imm:x}"
            if f3 == 4: return f"xori x{inst.rd},x{inst.rs1},0x{inst.imm:x}"
            return f"op_imm x{inst.rd},x{inst.rs1},{inst.imm}"
        if op == 0x33:
            f3 = inst.funct3
            if f3 == 0:
                return f"add x{inst.rd},x{inst.rs1},x{inst.rs2}" if inst.funct7 == 0 else f"sub x{inst.rd},x{inst.rs1},x{inst.rs2}"
            if f3 == 7: return f"and x{inst.rd},x{inst.rs1},x{inst.rs2}"
            if f3 == 6: return f"or x{inst.rd},x{inst.rs1},x{inst.rs2}"
            if f3 == 4: return f"xor x{inst.rd},x{inst.rs1},x{inst.rs2}"
            return f"alu_r x{inst.rd},x{inst.rs1},x{inst.rs2}"
        if op == 0x0B:
            return f"custom0 sel=0x{inst.imm:x}"
        if op == 0x03:  # LOAD
            return f"lw x{inst.rd},0x{inst.imm:x}(x{inst.rs1})"
        if op == 0x23:  # STORE
            return f"sw x{inst.rs2},0x{inst.imm:x}(x{inst.rs1})"
        if op == 0x63:  # BRANCH
            if inst.funct3 == 0: return f"beq x{inst.rs1},x{inst.rs2},0x{inst.imm:x}"
            if inst.funct3 == 1: return f"bne x{inst.rs1},x{inst.rs2},0x{inst.imm:x}"
            return f"branch 0x{inst.imm:x}"
        if op == 0x6F:  # JAL
            return f"jal x{inst.rd},0x{inst.imm:x}"
        if op == 0x67:  # JALR
            return f"jalr x{inst.rd},x{inst.rs1},0x{inst.imm:x}"
        if op == 0x0B:
            sel = inst.imm
            if sel == 0x10: return "vtrace_enter"
            if sel == 0x11: return "vtrace_exit"
            if sel == 0x12: return "vtrace_log"
            if sel == 0x13: return "vsync"
            if sel == 0x14: return "vassert"
            if sel == 0x15: return "vforce"
            if sel == 0x16: return "vrelease"
            return f"custom0 sel=0x{sel:x}"
        return f"0x{raw:08x}"

    # --- Function tracing wrappers (SCPUx_FN > per Firmware_Framework_Design spec) ---
    def fn_enter(self, func_name: str):
        """Call from demo or future 'firmware' simulation to emit SCPUx_FN > enter"""
        self.tracer.enter(func_name)

    def fn_exit(self, func_name: str):
        """Call from demo or future 'firmware' simulation to emit SCPUx_FN > exit"""
        self.tracer.exit(func_name)

    def fn_log(self, message: str):
        """Normal log with SCPUx > prefix (distinct from FN trace)"""
        self.tracer.log(message)

    def log(self, message: str):
        """Public logging method: stdout + dedicated file if open."""
        self._log(f"SCPU{self.cpu_id} > {message}")

    # --- Tracing context helpers ---
    @property
    def current_function(self) -> str | None:
        """Return the currently executing function name (from tracer stack), or None."""
        if hasattr(self, 'tracer') and self.tracer._call_stack:
            return self.tracer._call_stack[-1]
        return None

    @property
    def trace_depth(self) -> int:
        """Current function call depth."""
        if hasattr(self, 'tracer'):
            return self.tracer.current_depth
        return 0

    # --- WDT + Recovery support (core verification feature) ---
    def attach_recorder(self, recorder: Optional[TransactionRecorder] = None):
        if recorder is None:
            recorder = TransactionRecorder(max_records=256)
        self.recorder = recorder
        print(f"SCPU{self.cpu_id} > Transaction recorder attached")

    def attach_wdt(self, wdt: Optional[WatchdogTimer] = None, timeout: int = 10000):
        if wdt is None:
            wdt = WatchdogTimer(self.cpu_id, timeout=timeout)
            wdt.attach_recovery(self._default_wdt_recovery)
        self.wdt = wdt
        print(f"SCPU{self.cpu_id} > WDT attached (timeout={timeout})")

    def attach_instruction_tracer(self, tracer: Optional[InstructionTracer] = None, max_steps: int = 2048):
        """Attach a high-fidelity instruction tracer using a clean callback hook."""
        if tracer is None:
            tracer = InstructionTracer(self.cpu_id, max_steps=max_steps)

        def _callback(pc, raw, disasm, reg_changes):
            if tracer.enabled:
                tracer.record_step(pc=pc, raw=raw, disasm=disasm, reg_changes=reg_changes)

        self._trace_step_callback = _callback
        self.instr_tracer = tracer   # keep reference for user access
        print(f"SCPU{self.cpu_id} > Rich InstructionTracer attached via callback (max_steps={max_steps})")

    def _record_txn(self, txn):
        """Called by execution engine on every bus transaction."""
        if self.recorder is not None:
            self.recorder.record(txn)

    def _default_wdt_recovery(self, wdt, cpu):
        """Default recovery action when WDT fires (matches original spec)."""
        print(f"SCPU{self.cpu_id} > WDT recovery triggered - reset + full transaction replay + continue own code")
        self.recovery_count += 1

        if self.recorder and len(self.recorder) > 0:
            last = self.recorder.get_recent(1)[0]
            self._problem_addrs.add(last.address)

        # Use the improved reset + replay
        self.reset(replay_transactions=True)

        # Selective dummy mode for problematic addresses (as per original requirement)
        if self._problem_addrs:
            self.enter_dummy_mode()
            print(f"SCPU{self.cpu_id} > Entered dummy mode for suspect addrs: {[hex(a) for a in self._problem_addrs]}")

        wdt.reset()  # re-arm watchdog after recovery

    def wdt_tick(self):
        """Call this every step (or from external cycle model)."""
        if self.wdt:
            self.wdt.tick(self)

    def open_dedicated_log(self, path: str):
        """Open a dedicated log file for this CPU (SCPUx activity only)."""
        self.log_file = open(path, "a", buffering=1)
        self._log(f"SCPU{self.cpu_id} > Dedicated log opened: {path}")

    def _log(self, message: str):
        """Internal logging: prints to stdout + dedicated file if open."""
        print(message)
        if self.log_file:
            try:
                self.log_file.write(message + "\n")
            except Exception:
                pass

    # --- Force / Release Control (Verification Power Feature) ---
    def read_reg(self, index: int) -> int:
        """Read register, respecting active forces and X/Z sanitization."""
        from verif_cpu.utils.xz_sanitize import sanitize_if_xz

        if self.force_active and index in self.forced_regs:
            val = self.forced_regs[index]
            xz = getattr(self, "forced_regs_xz", {}).get(index, 0)
            return sanitize_if_xz(self, val, xz, self.bit_width, f"x{index} (forced)")
        val = self.regs.read(index)
        xz = self.regs.xz_mask(index)
        return sanitize_if_xz(self, val, xz, self.bit_width, f"x{index}")

    def write_reg(self, index: int, value: int):
        """Write register, respecting active forces (writes to forced regs are ignored)."""
        if self.force_active and index in self.forced_regs:
            self.log(f"[Force] Write to forced x{index} ignored (stays 0x{self.forced_regs[index]:08x})")
            return
        self.regs.write(index, value)

    def force_reg(self, reg: int, value: int, xz_mask: int = 0):
        self.forced_regs[reg] = value
        if xz_mask:
            if not hasattr(self, "forced_regs_xz"):
                self.forced_regs_xz: dict[int, int] = {}
            self.forced_regs_xz[reg] = xz_mask & ((1 << self.bit_width) - 1)
        self.log(f"[Force] x{reg} forced to 0x{value:08x}")

    def inject_reg_xz(self, reg: int, xz_mask: int):
        """Inject X/Z on register bits (verification stimulus)."""
        self.regs.inject_xz(reg, xz_mask)

    def release_reg(self, reg: int):
        if reg in self.forced_regs:
            del self.forced_regs[reg]
            self.log(f"[Release] x{reg} released from force")
        if hasattr(self, "forced_regs_xz") and reg in self.forced_regs_xz:
            del self.forced_regs_xz[reg]

    def force_mem(self, addr: int, value: int):
        self.forced_mem[addr] = value
        self.log(f"[Force] MEM[0x{addr:08x}] forced to 0x{value:08x}")

    def release_mem(self, addr: int):
        if addr in self.forced_mem:
            del self.forced_mem[addr]
            self.log(f"[Release] MEM[0x{addr:08x}] released")

    def set_force_active(self, active: bool):
        self.force_active = active
        self.log(f"[Force] Force mechanism {'ENABLED' if active else 'DISABLED'}")

    def _replay_recorded_transactions(self):
        """
        Replay all previously recorded bus transactions.
        This simulates the 'snoop during init → reset/hang → replay init txns → continue own code' flow.
        """
        if not self.recorder or len(self.recorder) == 0:
            return

        txns = self.recorder.get_recent(256)  # replay recent ones
        print(f"SCPU{self.cpu_id} > Replaying {len(txns)} recorded transactions...")

        for txn in txns:
            if txn.is_write and self.bus:
                try:
                    self.bus.write(txn.address, txn.data, txn.size)
                    self.log(f"[Replay] Write 0x{txn.address:08x} <= 0x{txn.data:08x}")
                except Exception as e:
                    self.log(f"[Replay] Write failed at 0x{txn.address:08x}: {e}")
            elif not txn.is_write and self.bus:
                try:
                    result = self.bus.read(txn.address, txn.size)
                    self.log(f"[Replay] Read  0x{txn.address:08x} => 0x{result.data:08x}")
                except Exception as e:
                    self.log(f"[Replay] Read failed at 0x{txn.address:08x}: {e}")

        print(f"SCPU{self.cpu_id} > Transaction replay complete. Continuing own firmware...")

    def attach_coverage_collector(self, collector):
        """Attach a CoverageCollector for assertion and coverage tracking."""
        self.coverage_collector = collector
        self.log("[Coverage] Collector attached")

    def attach_wave_dumper(self, dumper: Optional[WaveDumper] = None):
        """Attach a WaveDumper for firmware-controlled waveform dumping."""
        if dumper is None:
            dumper = WaveDumper(self.cpu_id)
        self.wave_dumper = dumper
        self.log("[Wave] WaveDumper attached")

    def get_metrics(self) -> dict:
        """Return a snapshot of key verification metrics for this CPU (used by reporting)."""
        cov = self.coverage_collector
        assert_summary = {}
        if cov and hasattr(cov, 'assertions'):
            for aid, res in cov.assertions.items():
                assert_summary[aid] = {
                    "total": res.total,
                    "passed": res.passed,
                    "failed": res.failed
                }
        return {
            "cpu_id": self.cpu_id,
            "name": getattr(self, 'name', f"CPU{self.cpu_id}"),
            "hierarchy": getattr(self, 'rtl_hierarchy', '') or getattr(self, 'hierarchy_id', None),
            "state": self.state,
            "final_pc": self.pc,
            "total_steps": self.total_steps,
            "recovery_count": self.recovery_count,
            "wdt_attached": self.wdt is not None,
            "wdt_fired": getattr(self.wdt, 'fired', False) if self.wdt else False,
            "bus_txns_recorded": len(self.recorder) if self.recorder else 0,
            "unique_pcs": len(cov.pc_hits) if cov else 0,
            "assertions": assert_summary,
            "has_instr_tracer": self.instr_tracer is not None,
            "instr_steps_traced": len(getattr(self.instr_tracer, '_steps', [])) if self.instr_tracer else 0,
        }

    def __repr__(self):
        return (f"VerifCPU(id={self.cpu_id}, width={self.bit_width}, "
                f"state={self.state}, pc=0x{self.pc:08x})")