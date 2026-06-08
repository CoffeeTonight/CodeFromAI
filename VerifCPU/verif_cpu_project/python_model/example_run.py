"""
VerifCPU Python Model - 간단 실행 예제

이 파일은 현재까지 만든 Python 모델을 실행해보는 예제입니다.
"""

from verif_cpu.core.cpu import VerifCPU
from verif_cpu.debug.console_interface import ConsoleDebugInterface

def main():
    print("=== VerifCPU Python Model Demo ===\n")

    # 3개의 CPU 생성 (ID: 1, 2, 3)
    cpus = {
        1: VerifCPU(1, 32),
        2: VerifCPU(2, 32),
        3: VerifCPU(3, 32),
    }

    # Hierarchy 정보 설정 (Runtime Config Memory 시뮬레이션)
    cpus[1].set_hierarchy(0x10)   # AHB Master 0
    cpus[2].set_hierarchy(0x20)   # AXI Master 1
    cpus[3].set_hierarchy(0x30)   # AHB Master 1

    # Console Debug Interface 생성
    console = ConsoleDebugInterface(cpus)

    # 콘솔 명령어 시뮬레이션
    commands = [
        "cpu 1 status",
        "cpu 2 stall",
        "cpu 0 status",
        "cpu 2 bus_write 0x12345678 0xdeadbeef 4",
        "cpu 3 bus_read 0xabcdef00 4",
        "cpu 2 resume",
        "cpu 0 status",
    ]

    for cmd in commands:
        print(f"\n> {cmd}")
        console.execute_command(cmd)

    print("\n=== Demo Finished ===")


if __name__ == "__main__":
    main()