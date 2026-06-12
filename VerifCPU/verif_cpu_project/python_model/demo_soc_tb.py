#!/usr/bin/env python3
"""
tb_dut — SoC + Master VCPU + Orchestrator + Slave VCPUs (behavior model demo).

Scenario (from architecture discussion):
  1. Phase A: SoC init traffic → slave VCPUs snoop/record on AXI taps
  2. Master releases Phase B → injects verification target addresses on bus
  3. Slaves collect bus_addr into per-CPU meta (unified mem)
  4. Host binds icode programs (program store) to slots
  5. Phase C: each slave runs icode via dispatcher (vicode_ret style loop)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verif_cpu.platform.addr_chg import AddrChanger
from verif_cpu.platform.agent import AgentConfig, MasterAgentCPU, VerifAgentCPU
from verif_cpu.platform.orchestrator import Phase, VerifOrchestrator
from verif_cpu.platform.unified_memory import ProgramStore, UnifiedMemoryLayout
from verif_cpu.soc.simple_soc import SimpleSoC, SocInitSequence


# --- Verification icode (program store — SoC/job specific, loaded at sim start) ---

def icode_check_sfr_ctrl(agent: VerifAgentCPU, bus_addr: int) -> bool:
    txn = agent.soc_ref.bus_read(bus_addr, 4)
    agent._log(f"    read 0x{bus_addr:08x} → 0x{txn.data:08x}")
    return txn.data == 0x0000_0001


def icode_check_sram_marker(agent: VerifAgentCPU, bus_addr: int) -> bool:
    txn = agent.soc_ref.bus_read(bus_addr, 4)
    agent._log(f"    read 0x{bus_addr:08x} → 0x{txn.data:08x}")
    return txn.data == 0xDEAD_BEEF


def icode_check_uart_baud(agent: VerifAgentCPU, bus_addr: int) -> bool:
    txn = agent.soc_ref.bus_read(bus_addr, 4)
    agent._log(f"    read 0x{bus_addr:08x} → 0x{txn.data:08x}")
    return txn.data == 0x0000_0080


def icode_probe_any(agent: VerifAgentCPU, bus_addr: int) -> bool:
    txn = agent.soc_ref.bus_read(bus_addr, 4)
    agent._log(f"    probe 0x{bus_addr:08x} → 0x{txn.data:08x}")
    return txn.resp == 0


# --- tb_dut: generate-style CPU list (like Verilog generate) ---

CPU_TABLE = [
    {"name": "MSTR", "id": 0, "role": "master", "tap": None},
    {"name": "SFR", "id": 1, "role": "slave", "tap": 0},
    {"name": "SRAM", "id": 2, "role": "slave", "tap": 1},
    {"name": "UART", "id": 3, "role": "slave", "tap": 2},
]

# Verification addresses master will inject (SoC-specific, runtime — not compile-time)
VERIFY_TARGETS = [
    0x4000_0000,  # SFR ctrl — seen at tap 0
    0x8000_0000,  # SRAM — tap 1
    0xC000_0000,  # UART — tap 2
]


def build_tb():
    soc = SimpleSoC()
    orch = VerifOrchestrator()
    mem = UnifiedMemoryLayout()
    addr_chg = AddrChanger(orch)
    prog = ProgramStore()

    ptr_sfr = prog.register("check_sfr_ctrl", icode_check_sfr_ctrl)
    ptr_sram = prog.register("check_sram_marker", icode_check_sram_marker)
    ptr_uart = prog.register("check_uart_baud", icode_check_uart_baud)

    slaves: list[VerifAgentCPU] = []
    master: MasterAgentCPU | None = None

    for entry in CPU_TABLE:
        cfg = AgentConfig(entry["id"], entry["name"], entry["role"], entry["tap"])
        if cfg.role == "master":
            master = MasterAgentCPU(cfg, orch, soc)
        else:
            agent = VerifAgentCPU(cfg, orch, mem, prog, addr_chg)
            agent.soc_ref = soc  # icode programs need bus access
            if cfg.tap_port_id is not None:
                soc.attach_snoop(cfg.tap_port_id, agent.on_bus_txn)
            slaves.append(agent)

    def on_orch_reset(cpu_mask: int, phase: Phase):
        for ag in slaves:
            off, ph = orch.acknowledge_reset(ag.cfg.cpu_id)
            ag.soft_reset(off, ph)

    orch.on_reset(on_orch_reset)
    return soc, orch, mem, prog, master, slaves


def run_campaign():
    print("=" * 72)
    print("tb_dut: SimpleSoC + VerifCPU agents (behavior model)")
    print("=" * 72)

    soc, orch, mem, prog, master, slaves = build_tb()
    slave_by_tap = {ag.cfg.tap_port_id: ag for ag in slaves}

    # --- Phase A: SoC init + slave logging (snoop active during init) ---
    print("\n[1] Phase A — SoC init + slave snoop")
    master.release_phase(Phase.INIT)
    soc.run_init(SocInitSequence.default_boot())
    for ag in slaves:
        ag.run_phase_a()
    print(f"    SoC init complete ({len(soc.init_log)} bus transactions)")

    # --- Phase B: master injects verify addresses ---
    print("\n[2] Phase B — master injects verification target addresses")
    master.release_phase(Phase.COLLECT)
    master.inject_verify_addresses(VERIFY_TARGETS)
    for ag in slaves:
        ag.run_current_phase()

    # --- Host bind: icode_ptr per slot (order-based, no compile-time addr map) ---
    print("\n[3] Host bind — icode_ptr → program store")
    bind_map = {
        0: prog.catalog[0][1],  # SFR tap → check_sfr
        1: prog.catalog[1][1],  # SRAM
        2: prog.catalog[2][1],  # UART
    }
    for ag in slaves:
        for i in range(ag.ctx.slot_count):
            tap = ag.cfg.tap_port_id
            if tap in bind_map:
                ag.ctx.slots[i].icode_ptr = bind_map[tap]
                print(
                    f"    CPU{ag.cfg.cpu_id} ({ag.cfg.name}) "
                    f"slot[{i}] icode_ptr=0x{bind_map[tap]:x}"
                )

    # --- Phase C: verify ---
    print("\n[4] Phase C — slave icode execution")
    master.release_phase(Phase.VERIFY)
    for ag in slaves:
        ag.run_current_phase()

    # --- Report ---
    print("\n" + "=" * 72)
    print("Campaign Report")
    print("=" * 72)
    total_pass = sum(ag.verify_pass for ag in slaves)
    total_fail = sum(ag.verify_fail for ag in slaves)
    for ag in slaves:
        s = ag.summary()
        print(
            f"  {s['name']:6s} (id={s['cpu_id']}) "
            f"txns={s['txn_recorded']:3d} slots={s['slots']} "
            f"PASS={s['verify_pass']} FAIL={s['verify_fail']}"
        )
    print(f"\n  TOTAL: PASS={total_pass} FAIL={total_fail}")
    print("=" * 72)

    if total_fail > 0:
        sys.exit(1)
    print("\n[SUCCESS] SoC verification campaign completed.")
    return total_pass, total_fail


if __name__ == "__main__":
    run_campaign()