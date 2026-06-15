"""
Waveform Dumper for VerifCPU

Provides firmware-controlled waveform dumping with support for
hierarchical scopes (similar to $dumpvars(0, specific_hierarchy) in simulators).

Firmware can control:
- When to start/stop dumping
- Which hierarchy/scope to include in the dump
"""

from typing import Optional, TextIO, Dict, List, Set
import time
from dataclasses import dataclass


@dataclass
class SignalDef:
    name: str
    width: int = 32
    scope: str = ""   # e.g. "CPU1/Regs" or "Bus/Master0"


class WaveDumper:
    """
    Records changes to important signals and supports exporting to VCD
    with proper hierarchical structure.

    Supports scoped dumping so that firmware can choose what part of the
    "design" (from the verification CPU's perspective) to dump.
    """

    # Wave command codes (used with vwave instruction)
    CMD_OFF = 0
    CMD_ON = 1
    CMD_DUMP_ALL = 2
    CMD_DUMP_SCOPE = 3          # arg = scope_id or hierarchy
    CMD_ADD_SCOPE = 4

    def __init__(self, cpu_id: int, enabled: bool = False):
        self.cpu_id = cpu_id
        self.enabled = enabled

        self._changes: List[tuple] = []           # (time, full_signal_name, value)
        self._signal_defs: Dict[str, SignalDef] = {}  # full_name -> definition

        self._active_scopes: Set[str] = set()     # which scopes are being dumped
        self._dump_all = True                     # if True, ignore active_scopes

        self._current_time = 0

    def handle_command(self, cmd: int, arg: int = 0):
        """Called from VWave custom instruction."""
        if cmd == self.CMD_ON:
            self.start()
        elif cmd == self.CMD_OFF:
            self.stop()
        elif cmd == self.CMD_DUMP_ALL:
            self.dump_all_scopes()
        elif cmd == self.CMD_DUMP_SCOPE:
            self.set_active_scope(str(arg))
        else:
            print(f"SCPU{self.cpu_id} > [WaveDumper] Unknown command: {cmd} (arg={arg})")

    # --- Control ---
    def start(self):
        if not self.enabled:
            self.enabled = True
            self._changes = []
            print(f"SCPU{self.cpu_id} > [Wave] Dumping started")

    def stop(self):
        if self.enabled:
            self.enabled = False
            print(f"SCPU{self.cpu_id} > [Wave] Dumping stopped")

    def set_active_scope(self, scope: str):
        """Only dump signals belonging to this scope (or its children)."""
        self._dump_all = False
        self._active_scopes = {scope}
        print(f"SCPU{self.cpu_id} > [Wave] Active dump scope set to: {scope}")

    def add_scope(self, scope: str):
        """Add a scope to the active dump set."""
        self._active_scopes.add(scope)
        self._dump_all = False
        print(f"SCPU{self.cpu_id} > [Wave] Added scope to dump: {scope}")

    def dump_all_scopes(self):
        self._dump_all = True
        self._active_scopes.clear()
        print(f"SCPU{self.cpu_id} > [Wave] Dumping ALL scopes")

    def tick(self, time_val: int):
        self._current_time = time_val

    # --- Signal Registration & Recording ---
    def register_signal(self, name: str, width: int = 32, scope: str = ""):
        """Register a signal under a specific scope (hierarchy)."""
        full_name = f"{scope}/{name}" if scope else name
        self._signal_defs[full_name] = SignalDef(name, width, scope)

    def record_change(self, signal: str, value: int, scope: str = ""):
        """Record a value change. Respects current active scopes."""
        if not self.enabled:
            return

        full_name = f"{scope}/{signal}" if scope else signal

        # Scope filtering
        if not self._dump_all:
            if not any(full_name.startswith(s) for s in self._active_scopes):
                return

        self._changes.append((self._current_time, full_name, value))

    # --- VCD Export with Hierarchy ---
    def export_vcd(self, filepath: str):
        if not self._changes:
            print(f"SCPU{self.cpu_id} > [Wave] No data to export.")
            return

        # Group signals by scope
        scopes: Dict[str, List[SignalDef]] = {}
        for full_name, sig in self._signal_defs.items():
            scope = sig.scope or "TOP"
            if scope not in scopes:
                scopes[scope] = []
            scopes[scope].append(sig)

        with open(filepath, "w") as f:
            self._write_vcd_header(f)
            self._write_vcd_scopes(f, scopes)
            self._write_vcd_values(f)
            self._write_vcd_changes(f)

        print(f"SCPU{self.cpu_id} > [Wave] Hierarchical VCD exported: {filepath} ({len(self._changes)} changes)")

    def _write_vcd_header(self, f: TextIO):
        f.write("$date\n    " + time.ctime() + "\n$end\n")
        f.write("$version\n    VerifCPU Python Model\n$end\n")
        f.write("$timescale 1ns $end\n\n")

    def _write_vcd_scopes(self, f: TextIO, scopes: Dict[str, List[SignalDef]]):
        for scope_name, signals in scopes.items():
            parts = scope_name.split('/')
            for i, part in enumerate(parts):
                indent = "  " * i
                f.write(f"{indent}$scope module {part} $end\n")

            for sig in signals:
                var_name = sig.name.replace('/', '_')
                f.write(f"  $var reg {sig.width} {var_name} {sig.name} $end\n")

            for i in reversed(range(len(parts))):
                indent = "  " * i
                f.write(f"{indent}$upscope $end\n")
        f.write("$enddefinitions $end\n\n")

    def _write_vcd_values(self, f: TextIO):
        # Initial values (simplified)
        f.write("$dumpvars\n")
        f.write("$end\n\n")

    def _write_vcd_changes(self, f: TextIO):
        last_time = -1
        for t, full_name, value in self._changes:
            if t != last_time:
                f.write(f"#{t}\n")
                last_time = t

            # Use a short identifier (in real VCD we'd use 1-letter codes, but this is readable)
            safe_name = full_name.replace('/', '_')[:16]
            f.write(f"b{value & 0xFFFFFFFF:032b} {safe_name}\n")

    def reset(self):
        self._changes.clear()
        self._current_time = 0
