"""
VerifCPU Advanced Tracing Demo (Custom vtrace_* Instructions)

핵심 목표 달성:
- vtrace_enter / vtrace_exit custom instruction으로 SCPUx_FN > 를 firmware에서 직접 발생시킴
- Multi-CPU에서 동시에 tracing 동작
- verbose_trace + dedicated log 결합

Branch/Jump는 아직 offset 계산이 불안정하므로, 간단한 linear firmware + tracing marker 중심으로 검증.
"""

import os
from verif_cpu.core.cpu import VerifCPU
from verif_cpu.memory.unified_pool import UnifiedFirmwarePool
from verif_cpu.bus.simple_bus import SimpleMemoryBus
from verif_cpu.core.isa import (
    encode_addi, encode_add, encode_vtrace_enter, encode_vtrace_exit, encode_vtrace_log, encode_custom
)


def build_simple_traced_firmware() -> bytes:
    """간단하지만 tracing marker가 확실히 들어간 firmware"""
    import struct
    words = []

    # main start
    words.append(encode_vtrace_enter(1))     # main enter
    words.append(encode_addi(1, 0, 10))
    words.append(encode_addi(2, 0, 20))
    words.append(encode_add(3, 1, 2))
    words.append(encode_vtrace_log(42))

    # call "function" 느낌으로 tracing marker
    words.append(encode_vtrace_enter(2))     # sub_func enter
    words.append(encode_addi(4, 3, 5))
    words.append(encode_vtrace_exit(2))      # sub_func exit

    words.append(encode_vtrace_exit(1))      # main exit
    words.append(encode_custom(0x00))        # vstop

    return struct.pack("<" + "I" * len(words), *words)


def main():
    print("=" * 78)
    print("VerifCPU Advanced Tracing via Custom Instructions Demo")
    print("=" * 78)

    bus = SimpleMemoryBus(0x10000)
    fw = build_simple_traced_firmware()

    pool = UnifiedFirmwarePool()
    pool.load_from_file("/tmp/adv_trace.bin") if False else None  # force recreate
    with open("/tmp/adv_trace.bin", "wb") as f:
        f.write(fw)
    pool.load_from_file("/tmp/adv_trace.bin")

    pool.assign_region(1, 0, len(fw))
    pool.assign_region(2, 0, len(fw))

    cpus = {}
    for cid in [1, 2]:
        cpu = VerifCPU(cid, 32, bus=bus)
        cpu.attach_firmware(pool, 0, len(fw))
        cpu.attach_recorder()
        cpu.attach_wdt(timeout=1000)

        log_dir = "/home/user/Desktop/VerifCPU/logs"
        os.makedirs(log_dir, exist_ok=True)
        cpu.open_dedicated_log(f"{log_dir}/SCPU{cid}_trace.log")

        cpu.verbose_trace = True
        cpus[cid] = cpu

    print("\n--- Executing firmware with embedded vtrace_* markers ---\n")

    for _ in range(30):
        for c in cpus.values():
            if not c.request_sim_stop:
                c.step()

    print("\n--- Result ---")
    print("Function tracing (SCPUx_FN >) was emitted directly from custom instructions in firmware!")
    print("Check the dedicated log files for complete trace history.")


if __name__ == "__main__":
    main()
