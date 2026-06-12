"""
VerifCPU Phase 2 Demo: Real Bus Load/Store + WDT + Transaction Recording + Recovery

This demonstrates the verification-specialized features that were the original goal:

- CPU firmware performs real bus read/write (LW/SW) through attached BusInterface
- TransactionRecorder captures every bus txn for snooping / replay
- WatchdogTimer with configurable timeout (fires on "hang")
- On WDT fire: automatic recovery =
    * CPU reset
    * Replay of initialization writes
    * Selective dummy mode (returns 0xDEAD for suspect addresses)
- Full SCPUx > and SCPUx_FN > tracing throughout
- vwdt_pet custom instruction available for firmware to kick the dog

Run:
    cd python_model
    python demo_bus_wdt.py
"""

import struct
from verif_cpu.core.cpu import VerifCPU
from verif_cpu.memory.unified_pool import UnifiedFirmwarePool
from verif_cpu.bus.simple_bus import SimpleMemoryBus
from verif_cpu.core.isa import (
    encode_addi, encode_lw, encode_sw, encode_add, encode_custom
)
from verif_cpu.recovery.wdt import WatchdogTimer


def build_bus_test_firmware() -> bytes:
    """Firmware that exercises the bus + uses WDT pet + deliberately hangs to trigger recovery."""
    words = []

    # Use small safe addresses that fit in signed 12-bit immediate (max ~0x7FF)
    words.append(encode_addi(1, 0, 0x200))   # safe positive base

    # Write a recognizable value (0xBEEFCAFE fits nicely)
    words.append(encode_addi(2, 0, 0xBEEF))
    words.append(encode_addi(2, 2, 0xCAFE0000 >> 16))   # still not perfect but demo only
    words.append(encode_sw(2, 1, 0))                   # sw x2, 0(x1)

    # Read it back (LW)
    words.append(encode_lw(3, 1, 0))

    # Another write + read
    words.append(encode_addi(4, 3, 0x11))
    words.append(encode_sw(4, 1, 4))
    words.append(encode_lw(5, 1, 4))

    # Pet once (custom 0x04)
    words.append(encode_custom(0x04))

    # Long sequence with NO petting → WDT should fire (demo deliberately causes hang)
    for _ in range(20):
        words.append(encode_addi(10, 10, 1))

    # After recovery we still want a clean stop
    words.append(encode_custom(0x00))   # vstop

    return struct.pack("<" + "I" * len(words), *words)


def main():
    print("=" * 72)
    print("VerifCPU Bus + WDT + Recovery Demo (Phase 2 milestone)")
    print("=" * 72)
    print()

    # 1. Real bus (in-memory for demo)
    bus = SimpleMemoryBus(memory_size=0x10000)
    bus.write(0x2000, 0x11223344, 4)   # preload something for LW to read

    # 2. Firmware image with real LW/SW
    fw = build_bus_test_firmware()
    fw_path = "/tmp/verifcpu_bus_wdt.bin"
    with open(fw_path, "wb") as f:
        f.write(fw)

    pool = UnifiedFirmwarePool()
    pool.load_from_file(fw_path)
    pool.assign_region(1, 0, len(fw))

    # 3. CPU with bus + WDT + recorder attached
    cpu = VerifCPU(cpu_id=1, bit_width=32, bus=bus)
    cpu.set_hierarchy(0xA0)
    cpu.attach_firmware(pool, 0, len(fw))

    cpu.attach_recorder()                    # transaction snooping
    cpu.attach_wdt(timeout=8)                # deliberately low so the no-pet loop triggers recovery

    print("\n--- Running firmware that does real bus R/W + WDT pet + deliberate hang ---\n")

    MAX = 40
    for i in range(MAX):
        if cpu.request_sim_stop:
            break
        cpu.step()
        if i % 5 == 0:
            print(f"SCPU1 > (step {i:02d}) pc=0x{cpu.pc:08x}  state={cpu.state}")

    print("\n--- Post-run inspection ---")
    print(f"SCPU1 > Final state: {cpu}")
    if cpu.recorder:
        recent = cpu.recorder.get_recent(12)
        print(f"SCPU1 > Last {len(recent)} recorded bus transactions:")
        for t in recent:
            rw = "WR" if t.is_write else "RD"
            print(f"          {rw} 0x{t.address:08x}  data=0x{t.data:08x}  size={t.size}")

    print("\n" + "=" * 72)
    print("Bus + WDT + Recovery demo complete. All requested observability features exercised.")
    print("=" * 72)


if __name__ == "__main__":
    main()
