"""
VerifCPU Verification Harness (Flagship Demo)

This is a realistic, reusable verification harness pattern built on top of VerifCPU.

It demonstrates how a verification engineer could actually use this Python model in practice:

- Multiple heterogeneous CPUs running different firmware
- Automatic high-fidelity instruction tracing (register deltas)
- Function-level tracing (SCPUx_FN >)
- WDT + automatic recovery with transaction replay
- Bus activity recording + smart queries
- Console-style runtime control (stall, bus R/W, WDT pet)
- Per-CPU dedicated logging
- Post-run analysis and reporting

This file is intended to be a starting point / template for real verification work.
"""

import os
from verif_cpu.core.cpu import VerifCPU
from verif_cpu.memory.unified_pool import UnifiedFirmwarePool
from verif_cpu.bus.simple_bus import SimpleMemoryBus
from verif_cpu.debug.console_interface import ConsoleDebugInterface
from verif_cpu.tracing.instruction_tracer import InstructionTracer
from verif_cpu.tracing.wave_dumper import WaveDumper
from verif_cpu.verification.coverage import CoverageCollector, attach_coverage
from verif_cpu.reporting import generate_campaign_report

from verif_cpu.core.isa import (
    encode_addi, encode_add, encode_sw, encode_lw,
    encode_vtrace_enter, encode_vtrace_exit, encode_vtrace_log,
    encode_vsync, encode_vassert, encode_vforce, encode_vrelease, encode_vwave, encode_custom
)


def build_firmware(role: str) -> bytes:
    """Generate different firmware depending on the CPU's role."""
    import struct
    words = []

    if role == "main":
        words.append(encode_vtrace_enter(100))
        words.append(encode_addi(1, 0, 0x2000))
        words.append(encode_addi(2, 0, 0x1111))
        words.append(encode_sw(2, 1, 0))
        words.append(encode_vtrace_enter(101))
        words.append(encode_addi(3, 2, 0x2222))
        words.append(encode_vtrace_exit(101))
        words.append(encode_lw(4, 1, 0))
        words.append(encode_vsync(1))                    # Multi-CPU sync point
        words.append(encode_vassert(1))                  # Self-check
        words.append(encode_vforce(1, 2))                # Request force
        words.append(encode_vrelease(1))                 # Request release
        words.append(encode_vwave(1))                    # Start dump
        words.append(encode_vwave(3, 0x10))              # Dump specific hierarchy (example)
        words.append(encode_vtrace_exit(100))
        words.append(encode_vwave(0))                    # Stop dump
        words.append(encode_custom(0x00))

    elif role == "worker":
        words.append(encode_vtrace_enter(200))
        words.append(encode_addi(10, 0, 0x3000))
        words.append(encode_addi(11, 0, 0xABCD))
        words.append(encode_sw(11, 10, 0))
        words.append(encode_vtrace_log(77))
        words.append(encode_vassert(42))       # Self-check example
        words.append(encode_vtrace_exit(200))
        words.append(encode_custom(0x00))

    elif role == "troublemaker":
        # Deliberately long sequence with very few exits → will trigger WDT
        words.append(encode_vtrace_enter(300))
        words.append(encode_addi(20, 0, 0x4000))
        for i in range(12):
            words.append(encode_addi(21, 21, 1))
            if i == 5:
                words.append(encode_vtrace_log(999))
        # Only one exit after many operations
        words.append(encode_vtrace_exit(300))
        words.append(encode_custom(0x00))

    return struct.pack("<" + "I" * len(words), *words)


def main():
    print("=" * 85)
    print("VerifCPU Verification Harness")
    print("Realistic multi-CPU verification scenario with full observability")
    print("=" * 85)
    print()

    # === Environment Setup ===
    bus = SimpleMemoryBus(0x100000)
    log_dir = "/home/user/Desktop/VerifCPU/logs/harness"
    os.makedirs(log_dir, exist_ok=True)

    # === Create CPUs with different roles ===
    roles = {
        1: "main",
        2: "worker",
        3: "troublemaker",   # This one will trigger WDT recovery
    }

    cpus = {}
    tracers = {}

    for cid, role in roles.items():
        fw_data = build_firmware(role)
        fw_path = f"/tmp/harness_fw_cpu{cid}.bin"
        with open(fw_path, "wb") as f:
            f.write(fw_data)

        pool = UnifiedFirmwarePool()
        pool.load_from_file(fw_path)
        pool.assign_region(cid, 0, len(fw_data))

        cpu = VerifCPU(cid, 32, bus=bus)
        cpu.set_hierarchy(0x10 * cid)

        cpu.attach_firmware(pool, 0, len(fw_data))
        cpu.attach_recorder()
        cpu.attach_wdt(timeout=6 if role == "troublemaker" else 5000)

        # Rich tracing
        tracer = InstructionTracer(cid, max_steps=512)
        cpu.attach_instruction_tracer(tracer)
        tracers[cid] = tracer

        # Coverage collection
        attach_coverage(cpu)

        # Waveform dumper with hierarchy support
        wave = WaveDumper(cid, enabled=True)
        cpu.attach_wave_dumper(wave)

        # Demonstrate scope control (using hierarchy_id)
        if cpu.hierarchy_id is not None:
            wave.set_active_scope(f"Hier{cpu.hierarchy_id:02x}")

        # Dedicated log
        cpu.open_dedicated_log(f"{log_dir}/SCPU{cid}.log")

        # Enable verbose for the main CPU
        if role == "main":
            cpu.verbose_trace = True

        cpu.name = role
        cpus[cid] = cpu

    console = ConsoleDebugInterface(cpus)

    print("=== Setup Complete ===")
    print("CPUs: main (1), worker (2), troublemaker (3 - will cause WDT timeout)")
    print("This harness demonstrates bus snooping + transaction recording + replay after reset.")
    print()

    # === Phase 1: Initial Console Control ===
    print("--- Phase 1: Initial Console Control ---")
    console.execute_command("cpu 2 stall")
    console.execute_command("cpu 1 bus_write 0x5000 0xCAFEBABE 4")
    console.execute_command("cpu 3 wdt_status")
    print()

    # === Phase 2: Run the scenario ===
    print("--- Phase 2: Running Multi-CPU Scenario ---")
    MAX_STEPS = 50
    for step in range(MAX_STEPS):
        for cid in sorted(cpus.keys()):
            cpu = cpus[cid]
            if cpu.request_sim_stop or cpu.state not in ("RUNNING", "DUMMY_MODE"):
                continue
            cpu.step()

        # Mid-run console intervention + explicit reset+replay demo
        if step == 18:
            print("\n>>> Console intervention at step 18 <<<")
            console.execute_command("cpu 2 resume")
            console.execute_command("cpu 1 wdt_pet")
            console.execute_command("cpu 3 bus_read 0x5000 4")
            print()

        # Demonstrate explicit reset + transaction replay on troublemaker
        if step == 25 and not cpus[3].request_sim_stop:
            print("\n>>> Explicit reset + full transaction replay on CPU3 (troublemaker) <<<")
            cpus[3].reset(replay_transactions=True)
            print("CPU3 reset complete with replay. It will now continue its own firmware.\n")

        if all(c.request_sim_stop for c in cpus.values()):
            break

    # === Phase 3: Post-run Analysis ===
    print("\n" + "=" * 85)
    print("POST-RUN ANALYSIS")
    print("=" * 85)

    for cid in sorted(cpus.keys()):
        cpu = cpus[cid]
        tracer = tracers[cid]
        role = roles[cid]

        print(f"\n[CPU {cid} - {role}]")
        print(f"  Final State : {cpu.state}")
        print(f"  Final PC    : 0x{cpu.pc:08x}")
        print(f"  Trace Depth : {cpu.trace_depth}")

        if cpu.recorder:
            recent = cpu.recorder.get_recent(3)
            print(f"  Recent Bus Txns: {len(recent)}")

        # Rich trace summary (now includes bus activity)
        steps = tracer.get_last_steps(6)
        if steps:
            print(f"  Recent rich trace steps (with bus effects where available):")
            for rec in steps[-4:]:
                delta_count = len(rec.reg_changes)
                bus_info = ""
                if rec.bus_addr is not None:
                    rw = "WR" if rec.bus_is_write else "RD"
                    bus_info = f"  [{rw} 0x{rec.bus_addr:08x}]"
                print(f"    Cycle {rec.cycle:3d}: {rec.disasm:25s} ({delta_count} reg changes){bus_info}")

        # Use new recorder query
        if cpu.recorder:
            recent_write = cpu.recorder.last_write_to(0x2000)
            if recent_write:
                print(f"  Last write touching 0x2000 area: 0x{recent_write.address:x} = 0x{recent_write.data:x}")

        # Coverage summary
        if cpu.coverage_collector:
            print(cpu.coverage_collector.summary())

        # Export waveform if dumper was used
        if cpu.wave_dumper:
            vcd_path = f"{log_dir}/SCPU{cid}.vcd"
            cpu.wave_dumper.export_vcd(vcd_path)

    # === Phase 4: Structured Campaign Report (NEW) ===
    print("\n" + "=" * 85)
    print("GENERATING STRUCTURED REPORT")
    print("=" * 85)

    # Build name-based map for the reporter (uses the 'roles' we defined)
    name_to_cpu = {roles[cid]: cpu for cid, cpu in cpus.items()}
    artifacts = {
        "log_dir": log_dir,
        "vcds": [f"{log_dir}/SCPU{cid}.vcd" for cid in cpus],
        "dedicated_logs": [f"{log_dir}/SCPU{cid}.log" for cid in cpus],
    }
    report = generate_campaign_report(name_to_cpu, artifacts=artifacts)

    report.print_summary()

    # Save rich reports
    json_path = f"{log_dir}/campaign_report.json"
    md_path = f"{log_dir}/campaign_report.md"
    report.save_json(json_path)
    report.save_markdown(md_path)
    print(f"\nReports saved:")
    print(f"  JSON: {json_path}")
    print(f"  MD  : {md_path}")

    print("\n" + "=" * 85)
    print("Harness run complete.")
    print("All dedicated logs are in:", log_dir)
    print("=" * 85)


if __name__ == "__main__":
    main()
