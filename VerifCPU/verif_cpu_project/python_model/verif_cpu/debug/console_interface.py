"""
Console Debug Interface (Python Model)

VCS/Xrun 콘솔에서 들어오는 명령을 해석하고 처리하는 모듈.
실제 구현에서는 DPI를 통해 SystemVerilog와 연결될 예정.
"""

from typing import Dict
from verif_cpu.core.cpu import VerifCPU


class ConsoleDebugInterface:
    def __init__(self, cpus: Dict[int, VerifCPU]):
        """
        cpus: {cpu_id: VerifCPU 객체}
        cpu_id == 0 은 '전체'를 의미
        """
        self.cpus = cpus

    def execute_command(self, cmd: str):
        """콘솔에서 들어온 명령어를 실행"""
        parts = cmd.strip().lower().split()
        if not parts or parts[0] != "cpu":
            print("Unknown command. Format: cpu <id> <command> ...")
            return

        if len(parts) < 3:
            print("Invalid command format.")
            return

        try:
            cpu_id = int(parts[1])
        except ValueError:
            print("CPU ID must be a number.")
            return

        command = parts[2]
        args = parts[3:]

        if cpu_id == 0:
            # 전체 CPU에 적용
            for cpu in self.cpus.values():
                self._dispatch(cpu, command, args)
        else:
            cpu = self.cpus.get(cpu_id)
            if cpu is None:
                print(f"CPU {cpu_id} not found.")
                return
            self._dispatch(cpu, command, args)

    def _dispatch(self, cpu: VerifCPU, command: str, args: list):
        if command == "stall":
            cpu.stall()
        elif command == "resume":
            cpu.resume()
        elif command == "status":
            print(cpu)
        elif command == "bus_write":
            if len(args) != 3:
                print("Usage: bus_write <addr> <data> <size>")
                return
            addr = int(args[0], 0)
            data = int(args[1], 0)
            size = int(args[2])

            if cpu.bus is None:
                cpu.log("[Console Bus Master] No bus attached!")
                return

            txn = cpu.bus.write(addr, data, size)
            if hasattr(cpu, '_record_txn'):
                cpu._record_txn(txn)

            status = "OK" if txn.resp == 0 else f"ERR{txn.resp}"
            cpu.log(f"[Console Bus Master] WRITE 0x{addr:08x} <= 0x{data:08x} (size={size}) -> {status}")
        elif command == "bus_read":
            if len(args) != 2:
                print("Usage: bus_read <addr> <size>")
                return
            addr = int(args[0], 0)
            size = int(args[1])

            if cpu.bus is None:
                cpu.log("[Console Bus Master] No bus attached!")
                return

            txn = cpu.bus.read(addr, size)
            if hasattr(cpu, '_record_txn'):
                cpu._record_txn(txn)

            status = "OK" if txn.resp == 0 else f"ERR{txn.resp}"
            cpu.log(f"[Console Bus Master] READ  0x{addr:08x} => 0x{txn.data:08x} (size={size}) -> {status}")
        elif command == "wdt_status":
            if cpu.wdt:
                cpu.log(f"[Console] {cpu.wdt.status()}")
            else:
                cpu.log("[Console] No WDT attached")
        elif command == "wdt_pet":
            if cpu.wdt:
                cpu.wdt.pet()
                cpu.log("[Console] WDT petted via console")
            else:
                cpu.log("[Console] No WDT attached")
        else:
            print(f"Unknown command for CPU{cpu.cpu_id}: {command}")


# 간단 테스트
if __name__ == "__main__":
    from verif_cpu.core.cpu import VerifCPU

    cpus = {i: VerifCPU(i) for i in range(1, 4)}
    console = ConsoleDebugInterface(cpus)

    console.execute_command("cpu 2 stall")
    console.execute_command("cpu 0 status")
    console.execute_command("cpu 1 bus_write 0x1000 0xdead 4")
    console.execute_command("cpu 3 bus_read 0x2000 4")
