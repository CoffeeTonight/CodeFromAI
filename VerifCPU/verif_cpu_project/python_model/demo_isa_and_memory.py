"""
Demo: Basic Integration of ISA + Custom Instructions + Unified Firmware Pool

This demonstrates the current state of D (structure) + C (memory pool).
"""

from verif_cpu.core.cpu import VerifCPU
from verif_cpu.memory.unified_pool import UnifiedFirmwarePool


def main():
    print("=== VerifCPU D + C Demo (ISA + Firmware Pool) ===\n")

    # 1. Prepare unified firmware pool
    pool = UnifiedFirmwarePool()

    # Create a dummy firmware file (4KB)
    firmware_data = bytearray(4096)
    # Put some marker bytes at different regions (for visibility)
    firmware_data[0:4] = b'\x13\x00\x00\x00'      # dummy instruction for CPU1
    firmware_data[1024:1028] = b'\x23\x00\x00\x00' # dummy for CPU2

    with open("/tmp/firmware.bin", "wb") as f:
        f.write(firmware_data)

    pool.load_from_file("/tmp/firmware.bin")

    # 2. Assign firmware regions to CPUs
    pool.assign_region(cpu_id=1, base_offset=0, size=512)
    pool.assign_region(cpu_id=2, base_offset=1024, size=512)

    # 3. Create CPUs and attach firmware
    cpu1 = VerifCPU(cpu_id=1, bit_width=32)
    cpu2 = VerifCPU(cpu_id=2, bit_width=32)

    cpu1.set_hierarchy(0x10)
    cpu2.set_hierarchy(0x20)

    cpu1.attach_firmware(pool, base_offset=0, size=512)
    cpu2.attach_firmware(pool, base_offset=1024, size=512)

    # 4. Run several steps
    print("\n--- Running steps ---")
    for i in range(6):
        cpu1.step()
        cpu2.step()
        print(f"Step {i+1}: {cpu1} | {cpu2}")

    print("\n=== Demo Finished ===")


if __name__ == "__main__":
    main()