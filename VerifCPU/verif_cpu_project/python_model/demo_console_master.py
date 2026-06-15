"""
VerifCPU Console Master Control Demo (Console Bus Master + Dedicated Logging)

이 데모는 사용자 원래 요구사항 중 핵심인
"vcs/xrun 콘솔에서 CPU stall + bus R/W 직접 제어" 를 Python 모델에서 현실적으로 구현한 것이다.

주요 기능:
- ConsoleDebugInterface가 진짜 "Console Bus Master" 역할 수행
- bus_write / bus_read 명령 → 실제 bus transaction 발생 + recorder 기록
- stall / resume / wdt_pet / wdt_status 등 콘솔에서 제어
- 각 CPU별 dedicated log file 지원 (모든 주요 이벤트 파일 기록)
- Multi-CPU 환경에서 동시에 제어 가능 (cpu 0 = all)

실행:
    cd /home/user/Desktop/VerifCPU/verif_cpu_project/python_model
    python demo_console_master.py
"""

import os
from verif_cpu.core.cpu import VerifCPU
from verif_cpu.bus.simple_bus import SimpleMemoryBus
from verif_cpu.debug.console_interface import ConsoleDebugInterface


def main():
    print("=" * 78)
    print("VerifCPU Console Bus Master + Dedicated Logging Demo")
    print("=" * 78)
    print()

    # 1. 공용 버스 + 3개 CPU 준비
    shared_bus = SimpleMemoryBus(memory_size=0x10000)

    # 미리 몇 개 값 preload (console read 테스트용)
    shared_bus.write(0x1000, 0xDEADBEEF, 4)
    shared_bus.write(0x2000, 0xCAFEBABE, 4)

    cpus = {}
    for i in range(1, 4):
        cpu = VerifCPU(cpu_id=i, bit_width=32, bus=shared_bus)
        cpu.set_hierarchy(0x10 * i)
        cpu.attach_recorder()
        cpu.attach_wdt(timeout=5000)   # 데모에서는 크게 해서 방해 안 되게

        # 각 CPU 전용 로그 파일 열기 (Desktop/VerifCPU/logs 안에)
        log_dir = "/home/user/Desktop/VerifCPU/logs"
        os.makedirs(log_dir, exist_ok=True)
        log_path = f"{log_dir}/SCPU{i}.log"
        cpu.open_dedicated_log(log_path)

        cpus[i] = cpu

    console = ConsoleDebugInterface(cpus)

    print("=== Console Commands Execution (simulating VCS/Xrun console) ===\n")

    commands = [
        "cpu 1 status",
        "cpu 2 stall",
        "cpu 0 status",                    # all
        "cpu 1 bus_write 0x3000 0x11223344 4",
        "cpu 3 bus_read 0x1000 4",
        "cpu 2 bus_write 0x4000 0xAABBCCDD 4",
        "cpu 1 wdt_status",
        "cpu 2 resume",
        "cpu 0 wdt_pet",
        "cpu 3 bus_read 0x2000 4",
        "cpu 1 bus_write 0x5000 0xFEEDFACE 4",
        "cpu 2 status",
    ]

    for cmd in commands:
        print(f"> {cmd}")
        console.execute_command(cmd)
        print()

    print("=== Post Demo Inspection ===")
    print("Recent transactions on CPU1 recorder (last 5):")
    if cpus[1].recorder:
        for t in cpus[1].recorder.get_recent(5):
            rw = "WR" if t.is_write else "RD"
            print(f"  {rw} 0x{t.address:08x} data=0x{t.data:08x}")

    print("\nDedicated log files created:")
    for i in range(1, 4):
        log_path = f"/home/user/Desktop/VerifCPU/logs/SCPU{i}.log"
        if os.path.exists(log_path):
            size = os.path.getsize(log_path)
            print(f"  {log_path}  ({size} bytes)")

    print("\n" + "=" * 78)
    print("Console Bus Master demo finished successfully.")
    print("You can now control VerifCPU instances from a simulated console,")
    print("perform real bus transactions, and have per-CPU dedicated logs.")
    print("=" * 78)


if __name__ == "__main__":
    main()
