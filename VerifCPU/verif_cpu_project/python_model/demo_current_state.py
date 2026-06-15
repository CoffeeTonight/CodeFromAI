"""
VerifCPU Current State Demo (D + C Progress)

This script demonstrates what has been built so far in pure Python:
- Configurable CPU (bit width, stall, dummy mode, hierarchy)
- ISA + Custom Instruction framework
- Unified Firmware Pool (file-based)
- Basic multi-CPU execution

Run this to see the current working skeleton.
"""

from verif_cpu.core.cpu import VerifCPU
from verif_cpu.memory.unified_pool import UnifiedFirmwarePool


def main():
    print("=== VerifCPU Current State Demo ===\n")

    # 1. Prepare a unified firmware image
    pool = UnifiedFirmwarePool()

    # Create a dummy firmware file (8KB)
    with open("/tmp/verif_fw.bin", "wb") as f:
        f.write(b"\x00" * 8192)

    pool.load_from_file("/tmp/verif_fw.bin")

    # 2. Assign firmware regions to CPUs (each gets 1KB)
    pool.assign_region(1, 0x000, 1024)
    pool.assign_region(2, 0x400, 1024)
    pool.assign_region(3, 0x800, 1024)

    # 3. Create three CPUs with different hierarchies (simulating different bus attachments)
    cpu1 = VerifCPU(1, 32)
    cpu2 = VerifCPU(2, 32)
    cpu3 = VerifCPU(3, 32)

    cpu1.set_hierarchy(0x10)   # e.g. AHB Master 0
    cpu2.set_hierarchy(0x20)   # e.g. AXI Master 0
    cpu3.set_hierarchy(0x30)   # e.g. AHB Master 1

    # 4. Attach each CPU to its firmware region
    cpu1.attach_firmware(pool, 0x000, 1024)
    cpu2.attach_firmware(pool, 0x400, 1024)
    cpu3.attach_firmware(pool, 0x800, 1024)

    print("\n--- Running 10 steps across 3 CPUs ---")
    for i in range(10):
        cpu1.step()
        cpu2.step()
        cpu3.step()
        print(f"Step {i+1:02d}: {cpu1} | {cpu2} | {cpu3}")

    print("\n=== Demo Finished ===")
    print("Current capabilities: CPU skeleton + ISA framework + Firmware Pool integration")


if __name__ == "__main__":
    main()