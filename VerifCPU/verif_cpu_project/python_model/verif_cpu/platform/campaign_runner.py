"""
Full campaign runner — behavior model aligned with verif_cpu_verilog/tb_full_campaign.v.

Verilog + VCD remains authoritative; this module mirrors TB phase order and checklist.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from verif_cpu.core.cpu import VerifCPU
from verif_cpu.debug.console_interface import ConsoleDebugInterface
from verif_cpu.memory.unified_pool import UnifiedFirmwarePool
from verif_cpu.platform.addr_chg import AddrChanger
from verif_cpu.platform.agent import AgentConfig, MasterAgentCPU, VerifAgentCPU
from verif_cpu.platform.campaign_layout import (
    CPU_POOL_WORD,
    OFF_PHASE_A,
    OFF_PHASE_B,
    OFF_PHASE_C,
    OFF_UART_HANG,
    OFF_UART_RECOVER,
    POOL_READMEMH_MAX_BYTES,
    POOL_WORD_ICODE,
    REGION_SIZE,
    VCPU_IMAGE_BYTES,
    pool_byte_base,
)
from verif_cpu.platform.campaign_manifest import VERIFY_MANIFEST, all_master_hints
from verif_cpu.platform.orchestrator import Phase, VerifOrchestrator
from verif_cpu.platform.soc_platform import (
    INIT_DONE_ADDR,
    INIT_DONE_MASK,
    INIT_DONE_POLL_MAX,
    INIT_DONE_VALUE,
)
from verif_cpu.platform.unified_memory import ProgramStore, UnifiedMemoryLayout
from verif_cpu.recovery.wdt import WatchdogTimer
from verif_cpu.soc.simple_soc import SimpleSoC, SocInitSequence
from verif_cpu.soc.soc_bus import SocBusAdapter
from verif_cpu.soc.soc_init_seq import SOC_INIT_STEPS
from verif_cpu.tracing.wave_dumper import WaveDumper
from verif_cpu.verification.campaign_vcd import (
    DEAD_HEX,
    export_cpu_vcd,
    export_main_campaign_vcd,
    run_vcd_gate,
)
from verif_cpu.verification.coverage import CoverageCollector, attach_coverage

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CAMPAIGN_BUILD = PROJECT_ROOT / "firmware" / "campaign" / "build"
ICODE_JSON = PROJECT_ROOT / "firmware" / "campaign" / "include" / "icode_map.json"
ICODE_POOL_BIN = CAMPAIGN_BUILD / "icode_pool.bin"
PY_VCD_DIR = PROJECT_ROOT / "python_model" / "sim_build"
PY_LOG_DIR = Path("/home/user/Desktop/VerifCPU/logs/full_campaign_py")

# Mirrors CAMPAIGN_ICODE_RV32_EXEC + CAMPAIGN_ICODE_MAP_BUS_CHECKS in tb_full_campaign_gen.vh
ICODE_RV32_EXEC = [
    (1, "check_sfr_ctrl", "Icode RV32 exec SFR slot0 (check_sfr_ctrl)"),
    (2, "check_sram_marker", "Icode RV32 exec SRAM slot0 (check_sram_marker)"),
    (3, "check_uart_baud", "Icode RV32 exec UART slot0 (check_uart_baud)"),
]

ICODE_MAP_BUS_CHECKS = [
    ("check_sfr_ctrl", 0x4000_0000, "Icode map SFR_CTRL"),
    ("check_sfr_mask", 0x4000_0004, "Icode map SFR_CFG"),
    ("check_sram_marker", 0x8000_0000, "Icode map SRAM_MARKER"),
    ("check_sram_aux", 0x8000_0004, "Icode map SRAM_AUX"),
    ("check_uart_baud", 0xC000_0000, "Icode map UART_BAUD"),
    ("check_uart_irq", 0xC000_0010, "Icode map UART_IRQ_HANG"),
]


@dataclass
class CampaignChecklist:
    items: list[tuple[str, bool]] = field(default_factory=list)

    def record(self, name: str, ok: bool) -> None:
        self.items.append((name, ok))

    def passed(self) -> int:
        return sum(1 for _, ok in self.items if ok)

    def failed(self) -> list[str]:
        return [n for n, ok in self.items if not ok]


def _assert_stats(cpu: VerifCPU) -> tuple[int, int]:
    cov = cpu.coverage_collector
    if not cov:
        return 0, 0
    passed = sum(r.passed for r in cov.assertions.values())
    failed = sum(r.failed for r in cov.assertions.values())
    return passed, failed


def run_cpu_from(cpu: VerifCPU, offset: int, max_steps: int = 2000) -> tuple[int, bool]:
    rec_before = cpu.recovery_count
    cpu.pc = offset
    cpu.state = "RUNNING"
    cpu.request_sim_stop = False
    cpu.regs.reset()
    if cpu.wdt:
        cpu.wdt.reset()
    if cpu.state == "DUMMY_MODE":
        cpu.exit_dummy_mode()
    steps = 0
    while steps < max_steps and cpu.state in ("RUNNING", "DUMMY_MODE"):
        if cpu.request_sim_stop:
            break
        cpu.step()
        steps += 1
    return steps, cpu.recovery_count > rec_before


def _make_icode_handler(expect: int) -> Callable[[VerifAgentCPU, int], bool]:
    def _fn(agent: VerifAgentCPU, bus_addr: int) -> bool:
        txn = agent.soc_ref.bus_read(bus_addr, 4)
        return txn.data == expect

    return _fn


def build_platform(
    soc: SimpleSoC,
    orch: VerifOrchestrator,
    mem: UnifiedMemoryLayout,
    prog: ProgramStore,
) -> tuple[MasterAgentCPU, list[VerifAgentCPU]]:
    addr_chg = AddrChanger(orch)
    slaves: list[VerifAgentCPU] = []

    master_cfg = AgentConfig(0, "MSTR", "master", None)
    master = MasterAgentCPU(
        master_cfg,
        orch,
        soc,
        init_done_addr=INIT_DONE_ADDR,
        init_done_mask=INIT_DONE_MASK,
        init_done_value=INIT_DONE_VALUE,
        poll_max=INIT_DONE_POLL_MAX,
    )

    for entry in VERIFY_MANIFEST:
        cfg = AgentConfig(entry["cpu_id"], entry["name"], "slave", entry["tap_port"])
        ag = VerifAgentCPU(cfg, orch, mem, prog, addr_chg)
        ag.soc_ref = soc
        soc.attach_snoop(entry["tap_port"], ag.on_bus_txn)
        slaves.append(ag)

    def on_orch_reset(cpu_mask: int, phase: Phase):
        for ag in slaves:
            off, ph = orch.acknowledge_reset(ag.cfg.cpu_id)
            ag.soft_reset(off, ph)

    orch.on_reset(on_orch_reset)
    return master, slaves


def _load_vcpu_image(name: str) -> bytes | None:
    path = CAMPAIGN_BUILD / f"{name}.bin"
    if not path.is_file():
        return None
    data = path.read_bytes()
    if len(data) > REGION_SIZE:
        raise ValueError(f"{path.name} exceeds REGION_SIZE ({len(data)} > {REGION_SIZE})")
    img = bytearray(REGION_SIZE)
    img[: len(data)] = data
    return bytes(img)


def _load_icode_map() -> dict:
    if not ICODE_JSON.is_file():
        return {"entries": [], "pool_bytes": 0}
    with open(ICODE_JSON, encoding="utf-8") as f:
        return json.load(f)


def _icode_entries_by_name() -> dict[str, dict]:
    data = _load_icode_map()
    return {e["name"]: e for e in data.get("entries", [])}


def _wire_icode_programs(prog: ProgramStore) -> dict[str, int]:
    """Bind manifest icode names to pool ptrs from icode_map.json (Verilog icode_map)."""
    ptrs: dict[str, int] = {}
    for e in _load_icode_map().get("entries", []):
        raw = e.get("pool_ptr", e.get("ptr", 0))
        ptr = int(raw, 0) if isinstance(raw, str) else int(raw)
        ptrs[e["name"]] = ptr

    prog.programs.clear()
    prog.catalog.clear()
    for entry in VERIFY_MANIFEST:
        for t in entry["targets"]:
            name = t["icode"]
            ptr = ptrs.get(name, 0x1000 * (len(prog.catalog) + 1))
            prog.programs[ptr] = _make_icode_handler(t["expect"])
            prog.catalog.append((name, ptr))
    return ptrs


def _unified_pool_bytes(icode_pool_bytes: int) -> int:
    icode_end = pool_byte_base(POOL_WORD_ICODE) + icode_pool_bytes
    return max(VCPU_IMAGE_BYTES, icode_end)


def _embed_icode_pool(pool: UnifiedFirmwarePool, icode_blob: bytes) -> None:
    icode_base = pool_byte_base(POOL_WORD_ICODE)
    needed = icode_base + len(icode_blob)
    if len(pool._data) < needed:
        pool._data.extend(b"\x00" * (needed - len(pool._data)))
    pool._data[icode_base : icode_base + len(icode_blob)] = icode_blob


def _check_icode_pool_embedded(pool: UnifiedFirmwarePool) -> bool:
    icode_base = pool_byte_base(POOL_WORD_ICODE)
    if icode_base + 4 > len(pool._data):
        return False
    word = int.from_bytes(pool._data[icode_base : icode_base + 4], "little")
    return word != 0x0000_0013


def _bus_txn_count(cpu: VerifCPU) -> int:
    return len(cpu.recorder) if cpu.recorder else 0


def exec_icode_on_cpu(
    cpu: VerifCPU,
    pool: UnifiedFirmwarePool,
    icode_ptr: int,
    icode_pool_sz: int,
    max_steps: int = 48,
) -> bool:
    """Mirror tb_full_campaign_gen.vh exec_icode_on_cpu task."""
    cid = cpu.cpu_id
    saved_base, saved_size = pool.get_region(cid)
    icode_base = pool_byte_base(POOL_WORD_ICODE)
    pool.assign_region(cid, icode_base, icode_pool_sz)

    txn_before = _bus_txn_count(cpu)
    cpu.pc = icode_ptr
    cpu.state = "RUNNING"
    cpu.request_sim_stop = False
    cpu.regs.reset()
    if cpu.wdt:
        cpu.wdt.reset()

    steps = 0
    while steps < max_steps and cpu.state in ("RUNNING", "DUMMY_MODE"):
        if cpu.request_sim_stop:
            break
        cpu.step()
        steps += 1

    ok = cpu.request_sim_stop and _bus_txn_count(cpu) > txn_before
    pool.assign_region(cid, saved_base, saved_size)
    return ok


def check_icode_map_bus_addrs() -> list[tuple[str, bool]]:
    by_name = _icode_entries_by_name()
    results: list[tuple[str, bool]] = []
    for name, expect_addr, label in ICODE_MAP_BUS_CHECKS:
        entry = by_name.get(name)
        got = int(entry["bus_addr"]) if entry else -1
        results.append((label, got == expect_addr))
    return results


def bind_agent_icodes(agents: list[VerifAgentCPU], prog: ProgramStore) -> None:
    from verif_cpu.platform.campaign_manifest import icode_bind_by_tap

    name_to_ptr = {n: p for n, p in prog.catalog}
    bind = icode_bind_by_tap()
    for ag in agents:
        if ag.cfg.tap_port_id is None:
            continue
        for i, nm in enumerate(bind[ag.cfg.tap_port_id]):
            if i < ag.ctx.slot_count:
                ag.ctx.slots[i].icode_ptr = name_to_ptr.get(nm, 0)


def run_multi_icode_rounds(
    soc: SimpleSoC,
    agents: list[VerifAgentCPU],
    orch: VerifOrchestrator,
) -> tuple[int, int, bool, bool]:
    """Mirror CAMPAIGN_ICODE_AGENT_ROUNDS — bus_read then agent phase_c per slot."""
    max_slots = max((ag.ctx.slot_count for ag in agents), default=0)
    inter_reset_ok = True
    round0_pass_ok = False

    for slot_i in range(max_slots):
        if slot_i > 0:
            rst_before = orch.reset_count
            orch.icode_inter_reset()
            if orch.reset_count <= rst_before:
                inter_reset_ok = False

        for ag in agents:
            if slot_i < ag.ctx.slot_count:
                addr = ag.ctx.slots[slot_i].bus_addr
                soc.bus_read(addr, 4)
                ag.run_phase_c_slot(slot_i)

        if slot_i == 0:
            round0_pass_ok = sum(ag.verify_pass for ag in agents) == 3

    total_pass = sum(ag.verify_pass for ag in agents)
    total_fail = sum(ag.verify_fail for ag in agents)
    return total_pass, total_fail, inter_reset_ok, round0_pass_ok


def setup_vcpus(soc: SimpleSoC, pool: UnifiedFirmwarePool) -> dict[int, VerifCPU]:
    icode_map = _load_icode_map()
    icode_pool_bytes = int(icode_map.get("pool_bytes", 0))

    if not ICODE_POOL_BIN.is_file():
        raise FileNotFoundError(
            f"Missing {ICODE_POOL_BIN} — run firmware/campaign build_icode_pool.py"
        )
    icode_blob = ICODE_POOL_BIN.read_bytes()
    if icode_pool_bytes and len(icode_blob) != icode_pool_bytes:
        icode_pool_bytes = len(icode_blob)

    pool._data = bytearray(_unified_pool_bytes(icode_pool_bytes))
    _embed_icode_pool(pool, icode_blob)

    cpus: dict[int, VerifCPU] = {}
    for entry in VERIFY_MANIFEST:
        cid = entry["cpu_id"]
        name = entry["name"]
        tap = entry["tap_port"]
        cpu = VerifCPU(cid, bus=SocBusAdapter(soc, tap_port_id=tap))
        cpu.name = name
        cpu.trace_enabled = False
        cpu.attach_recorder()
        wdt = WatchdogTimer(cid, timeout=100, auto_recovery=True)
        wdt.attach_recovery(cpu._default_wdt_recovery)
        cpu.attach_wdt(wdt)
        cpu.attach_wave_dumper(WaveDumper(cid))
        attach_coverage(cpu, CoverageCollector(cid))
        cpus[cid] = cpu

    for entry in VERIFY_MANIFEST:
        cid = entry["cpu_id"]
        blob = _load_vcpu_image(entry["name"])
        if blob is None:
            raise FileNotFoundError(
                f"Missing {entry['name']}.bin in {CAMPAIGN_BUILD} — run firmware/campaign make"
            )
        base = pool_byte_base(CPU_POOL_WORD[cid])
        pool._data[base : base + len(blob)] = blob
        pool.assign_region(cid, base, REGION_SIZE)
        cpus[cid].attach_firmware(pool, base, REGION_SIZE)
    return cpus


def export_campaign_vcds(
    cpus: dict[int, VerifCPU],
    agents: list[VerifAgentCPU],
    orch: VerifOrchestrator,
    *,
    success: bool,
    log_dir: Path | None = None,
) -> tuple[Path, list[Path]]:
    """Mirror CAMPAIGN_VCD_EXPORT + vcd_marker stamp."""
    log_dir = log_dir or PY_LOG_DIR
    main_vcd = PY_VCD_DIR / "tb_full_campaign.vcd"
    vcd_marker = DEAD_HEX if success else 0xBADC0DE
    agent_pass = [ag.verify_pass for ag in agents]
    while len(agent_pass) < 3:
        agent_pass.append(0)

    export_main_campaign_vcd(
        main_vcd,
        vcd_marker=vcd_marker,
        orch_reset_count=orch.reset_count,
        agent_verify_pass=agent_pass,
        dead_samples=[DEAD_HEX],
    )

    cpu_vcds: list[Path] = []
    for cid in (1, 2, 3):
        out = log_dir / f"SCPU{cid}.vcd"
        export_cpu_vcd(out, cid, cpus[cid].pc)
        cpu_vcds.append(out)

    return main_vcd, cpu_vcds


def run_full_campaign() -> int:
    print("=" * 72)
    print("PYTHON MODEL CAMPAIGN — aligned with verif_cpu_verilog/tb_full_campaign.v")
    print("=" * 72)

    checklist = CampaignChecklist()
    soc = SimpleSoC()
    orch = VerifOrchestrator()
    mem = UnifiedMemoryLayout()
    prog = ProgramStore()
    pool = UnifiedFirmwarePool()

    icode_map = _load_icode_map()
    icode_pool_bytes = int(icode_map.get("pool_bytes", 0))
    icode_by_name = _icode_entries_by_name()

    master, agents = build_platform(soc, orch, mem, prog)
    _wire_icode_programs(prog)
    cpus = setup_vcpus(soc, pool)

    init_steps = len(SOC_INIT_STEPS)

    # Firmware load gate (readmemh embed policy)
    use_lazy = icode_pool_bytes > POOL_READMEMH_MAX_BYTES
    if use_lazy:
        checklist.record("Icode pool embedded (readmemh)", False)
    else:
        checklist.record("Icode pool embedded (readmemh)", _check_icode_pool_embedded(pool))

    # [1] Phase A — SoC init + VCPU + agent snoop
    print("\n[1] Phase A — SoC init + VCPU + agent snoop")
    orch.phase_release(Phase.INIT, OFF_PHASE_A)
    soc.run_init(SocInitSequence(steps=list(SOC_INIT_STEPS)))
    for ag in agents:
        ag.run_phase_a()
    for entry in VERIFY_MANIFEST:
        run_cpu_from(cpus[entry["cpu_id"]], OFF_PHASE_A, max_steps=64)
    checklist.record(
        f"Phase A SoC init ({init_steps}-step)",
        len(soc.init_log) >= init_steps,
    )

    # [2] Phase B — master init_done gate + hints + collect
    print("\n[2] Phase B — master hints + collect")
    checklist.record("Master SoC init_done poll", master.wait_soc_init_done())
    orch.phase_release(Phase.COLLECT, OFF_PHASE_B)
    master.inject_verify_manifest()
    for ag in agents:
        ag.run_phase_b()
    for entry in VERIFY_MANIFEST:
        run_cpu_from(cpus[entry["cpu_id"]], OFF_PHASE_B, max_steps=48)
    checklist.record(
        "Phase B multi-slots (2 per agent)",
        all(ag.ctx.slot_count >= 2 for ag in agents),
    )

    # [3] Console stall/resume
    print("\n[3] Console stall / bus_write / resume")
    console = ConsoleDebugInterface(cpus)
    console.execute_command("cpu 1 stall")
    console.execute_command("cpu 1 bus_write 0x40000008 0xCAFE 4")
    console.execute_command("cpu 1 resume")
    checklist.record("Console stall/resume", cpus[1].state == "RUNNING")

    # [4][5] Phase C — SFR / SRAM VCPU firmware
    print("\n[4] Phase C — SFR full RV32I + custom")
    orch.phase_release(Phase.VERIFY, OFF_PHASE_C)
    run_cpu_from(cpus[1], OFF_PHASE_C, max_steps=900)
    sfr_ap, sfr_af = _assert_stats(cpus[1])
    checklist.record("SFR assertions pass", sfr_af == 0 and sfr_ap >= 3)
    checklist.record("SFR bus activity", _bus_txn_count(cpus[1]) >= 3)

    print("\n[5] Phase C — SRAM JAL/JALR")
    run_cpu_from(cpus[2], OFF_PHASE_C, max_steps=400)
    sram_ap, sram_af = _assert_stats(cpus[2])
    checklist.record("SRAM assertions pass", sram_af == 0)

    # [6] Platform icode — RV32 pool exec + multi-slot + inter-reset
    print("\n[6] Platform icode — RV32 pool exec + multi-slot dispatch + inter-reset")
    for cid, icode_name, label in ICODE_RV32_EXEC:
        entry = icode_by_name.get(icode_name, {})
        ptr = int(entry.get("pool_ptr", 0))
        ok = exec_icode_on_cpu(cpus[cid], pool, ptr, icode_pool_bytes, max_steps=48)
        checklist.record(label, ok)

    for label, ok in check_icode_map_bus_addrs():
        checklist.record(label, ok)

    bind_agent_icodes(agents, prog)
    agent_pass, agent_fail, inter_reset_ok, round0_pass_ok = run_multi_icode_rounds(
        soc, agents, orch
    )
    checklist.record("Icode inter-reset pulse", inter_reset_ok)
    checklist.record("Multi-icode round0 PASS=3", round0_pass_ok)
    checklist.record("Platform multi-icode PASS=6", agent_fail == 0 and agent_pass == 6)
    checklist.record("Orchestrator reset count", orch.reset_count >= 4)

    # [7] UART WDT hang + recovery
    print("\n[7] UART WDT hang → recovery → recover fw")
    _, hang_recovery = run_cpu_from(cpus[3], OFF_UART_HANG, max_steps=200)
    run_cpu_from(cpus[3], OFF_UART_RECOVER, max_steps=300)
    checklist.record("WDT hang recovery", hang_recovery)
    uart_ap, uart_af = _assert_stats(cpus[3])
    checklist.record("UART recover assertions", uart_af == 0)
    checklist.record("DEADDEAD recovery path", cpus[3].recovery_count >= 1)

    campaign_ok = not checklist.failed()

    # [8] VCD export gate
    print("\n[8] VCD export")
    main_vcd, cpu_vcds = export_campaign_vcds(
        cpus, agents, orch, success=campaign_ok
    )
    checklist.record("Main VCD path set", main_vcd.is_file())

    vcd_ok, vcd_msgs = run_vcd_gate(main_vcd, cpu_vcds)
    checklist.record("VCD export gate (verify_vcd)", vcd_ok if campaign_ok else True)
    for line in vcd_msgs:
        print(f"  {line}")

    # Report
    print("\n" + "=" * 72)
    print("CAMPAIGN REPORT (Python model)")
    print("=" * 72)
    for entry in VERIFY_MANIFEST:
        c = cpus[entry["cpu_id"]]
        m = c.get_metrics()
        ap, af = _assert_stats(c)
        print(
            f"  {c.name:5s} steps={m['total_steps']:4d} bus={m['bus_txns_recorded']:3d} "
            f"assert_pass={ap} fail={af}"
        )
    print(f"  Agents PASS={agent_pass} FAIL={agent_fail}")
    print(f"  Checklist: {checklist.passed()}/{len(checklist.items)} passed")
    for name, ok in checklist.items:
        print(f"    [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"  VCD: {main_vcd}")

    if checklist.failed():
        print("\n[FAIL] Python model campaign incomplete.")
        return 1
    print("\n[SUCCESS] Python model campaign passed (Verilog-aligned reference).")
    return 0