"""
Multi-CPU Demo with Unified Firmware Pool + Basic Custom Instruction Dispatch

This shows the current state of the VerifCPU Python model (D + C progress).
"""

from verif_cpu.core.cpu import VerifCPU
from verif_cpu.memory.unified_pool import UnifiedFirmwarePool


def main():
    print("=== VerifCPU Multi-CPU Demo ===\n")

    pool = UnifiedFirmwarePool()

    # Create a dummy firmware file (8KB)
    with open("/tmp/fw_multi.bin", "wb") as f:
        f.write(b"\x00" * 8192)

    pool.load_from_file("/tmp/fw_multi.bin")

    # Assign different regions to different CPUs
    pool.assign_region(1, 0x000, 1024)
    pool.assign_region(2, 0x400, 1024)
    pool.assign_region(3, 0x800, 1024)

    # Create 3 CPUs with different hierarchies
    cpu1 = VerifCPU(1, 32)
    cpu2 = VerifCPU(2, 32)
    cpu3 = VerifCPU(3, 32)

    cpu1.set_hierarchy(0x10)
    cpu2.set_hierarchy(0x20)
    cpu3.set_hierarchy(0x30)

    cpu1.attach_firmware(pool, 0x000, 1024)
    cpu2.attach_firmware(pool, 0x400, 1024)
    cpu3.attach_firmware(pool, 0x800, 1024)

    print("\n--- Running 8 steps across 3 CPUs ---")
    for i in range(8):
        cpu1.step()
        cpu2.step()
        cpu3.step()
        print(f"Step {i+1:02d}: {cpu1} | {cpu2} | {cpu3}")

    print("\n=== Demo Finished ===")


if __name__ == "__main__":
    main()