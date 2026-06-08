"""
VerifCPU Verification Scenario Demo (종합 데모 - Phase 4)

이 데모는 지금까지 개발한 VerifCPU의 거의 모든 기능을 결합하여
"실제 검증 프로젝트에서 VerifCPU를 어떻게 활용할 수 있는지" 보여준다.

시연하는 기능:
- Multi-CPU (3개) : 서로 다른 hierarchy에 attach된 bus master 시뮬레이션
- Advanced Function Tracing (vtrace_* custom instr + robust call stack)
- Real bus activity (LW/SW) + TransactionRecorder
- WDT + 자동 Recovery (한 CPU에서 timeout 유발)
- Console Bus Master (selective stall, bus inspection, wdt control)
- Per-CPU Dedicated Log Files
- verbose_trace로 상태 관찰

이 데모를 실행하면 "이런 식으로 실제 SoC 검증에 쓰일 수 있겠다"는 느낌을 받을 수 있다.
"""

import os
from verif_cpu.core.cpu import VerifCPU
from verif_cpu.memory.unified_pool import UnifiedFirmwarePool
from verif_cpu.bus.simple_bus import SimpleMemoryBus
from verif_cpu.debug.console_interface import ConsoleDebugInterface
from verif_cpu.core.isa import (
    encode_addi, encode_add, encode_lw, encode_sw,
    encode_vtrace_enter, encode_vtrace_exit, encode_vtrace_log,
    encode_custom
)


def build_cpu_firmware(cpu_id: int) -> bytes:
    """각 CPU별로 조금씩 다른 firmware (tracing marker 포함)"""
    import struct
    words = []

    # === Entry ===
    words.append(encode_vtrace_enter(10 + cpu_id))   # cpu-specific main

    words.append(encode_addi(1, 0, 0x100 * cpu_id))  # base addr
    words.append(encode_addi(2, 0, 0xBEEF + cpu_id))
    words.append(encode_sw(2, 1, 0))                 # bus write

    words.append(encode_vtrace_enter(20 + cpu_id))   # inner function
    words.append(encode_addi(3, 2, 1))
    words.append(encode_vtrace_log(cpu_id * 10))
    words.append(encode_vtrace_exit(20 + cpu_id))

    words.append(encode_lw(4, 1, 0))                 # bus read back

    # CPU 2는 일부러 WDT를 유발하기 위해 긴 루프 (pet 없이)
    if cpu_id == 2:
        for _ in range(12):
            words.append(encode_addi(10, 10, 1))

    words.append(encode_vtrace_exit(10 + cpu_id))
    words.append(encode_custom(0x00))                # vstop

    return struct.pack("<" + "I" * len(words), *words)


def main():
    print("=" * 82)
    print("VerifCPU Full Verification Scenario Demo")
    print("Multi-CPU + Advanced Tracing + Bus + WDT Recovery + Console Control")
    print("=" * 82)
    print()

    # === 1. 공용 버스 준비 ===
    bus = SimpleMemoryBus(0x20000)

    # === 2. Firmware 준비 (CPU별 약간 다름) ===
    firmwares = {}
    for cid in [1, 2, 3]:
        fw = build_cpu_firmware(cid)
        path = f"/tmp/verif_scenario_cpu{cid}.bin"
        with open(path, "wb") as f:
            f.write(fw)
        firmwares[cid] = (path, fw)

    pool = UnifiedFirmwarePool()
    # pool은 파일 하나만 로드할 수 있으므로, 각 CPU별로 별도 pool을 쓰거나
    # 하나의 큰 이미지에 offset으로 배치하는 게 맞지만, 여기서는 단순화를 위해
    # 각 CPU가 자신의 firmware 파일을 독립적으로 사용하게 한다.
    # (실제로는 UnifiedPool이지만 demo에서는 편의상 별도 로드)

    # === 3. 3개 CPU 생성 (모두 기능 full attach) ===
    cpus = {}
    for cid in [1, 2, 3]:
        cpu = VerifCPU(cid, 32, bus=bus)
        cpu.set_hierarchy(0x10 * cid)

        # 각자 dedicated firmware (간단히 별도 attach 방식)
        path, fw = firmwares[cid]
        p = UnifiedFirmwarePool()
        p.load_from_file(path)
        p.assign_region(cid, 0, len(fw))
        cpu.attach_firmware(p, 0, len(fw))

        cpu.attach_recorder()
        cpu.attach_wdt(timeout=8 if cid == 2 else 5000)   # CPU2만 WDT를 쉽게 터지게

        # Dedicated log
        log_dir = "/home/user/Desktop/VerifCPU/logs"
        os.makedirs(log_dir, exist_ok=True)
        cpu.open_dedicated_log(f"{log_dir}/SCPU{cid}_scenario.log")

        cpu.verbose_trace = (cid == 1)   # CPU1만 verbose
        cpus[cid] = cpu

    console = ConsoleDebugInterface(cpus)

    print("=== Initial Setup Complete ===")
    print("CPUs 1,2,3 created with full features (tracing, WDT, recorder, dedicated logs)")
    print("CPU2 has very low WDT timeout to demonstrate recovery.\n")

    # === 4. Console 명령으로 초기 제어 ===
    print("--- Console Pre-control ---")
    console.execute_command("cpu 3 stall")
    console.execute_command("cpu 1 bus_write 0x8000 0xDEADBEEF 4")
    console.execute_command("cpu 2 wdt_status")
    print()

    # === 5. 실제 실행 (Multi-CPU 동시) ===
    print("--- Running Multi-CPU Scenario (CPU2 will trigger WDT recovery) ---\n")

    MAX = 45
    for step in range(MAX):
        for cid in [1, 2, 3]:
            c = cpus[cid]
            if c.request_sim_stop or c.state not in ("RUNNING", "DUMMY_MODE"):
                continue
            c.step()

        # 중간에 console로 개입 (demo용)
        if step == 18:
            print("\n>>> Console intervention at step 18 <<<")
            console.execute_command("cpu 3 resume")
            console.execute_command("cpu 1 wdt_pet")
            console.execute_command("cpu 3 bus_read 0x8000 4")
            print()

        if all(c.request_sim_stop for c in cpus.values()):
            break

    # === 6. 결과 요약 ===
    print("\n" + "=" * 82)
    print("Scenario Complete - Summary")
    print("=" * 82)

    for cid in [1, 2, 3]:
        c = cpus[cid]
        print(f"\n[CPU{cid}]")
        print(f"  Final state: {c.state}, pc=0x{c.pc:08x}")
        if c.recorder:
            recent = c.recorder.get_recent(3)
            print(f"  Recent bus txns: {len(recent)}")
        if c.wdt:
            print(f"  WDT: {c.wdt.status()}")

    print("\nDedicated scenario logs:")
    for cid in [1, 2, 3]:
        p = f"/home/user/Desktop/VerifCPU/logs/SCPU{cid}_scenario.log"
        if os.path.exists(p):
            print(f"  {p} ({os.path.getsize(p)} bytes)")

    print("\nThis demo showed:")
    print("  - Multi-CPU concurrent execution with individual firmware")
    print("  - Robust SCPUx_FN > tracing from custom instructions")
    print("  - Real bus activity + recording")
    print("  - WDT timeout + automatic recovery on one CPU")
    print("  - Console Bus Master controlling everything live")
    print("  - Per-CPU dedicated logging")


if __name__ == "__main__":
    main()
