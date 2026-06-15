"""
Basic Demo of VerifCPU Python Model

This shows the current state of the core CPU, stall/resume, and dummy mode.
"""

from verif_cpu.core.cpu import VerifCPU
from verif_cpu.bus.simple_bus import SimpleMemoryBus


def main():
    print("=== VerifCPU Basic Demo ===\n")

    # Create a simple memory bus (for testing)
    bus = SimpleMemoryBus()

    # Create two CPUs with different bit widths
    cpu1 = VerifCPU(cpu_id=1, bit_width=32, bus=bus)
    cpu2 = VerifCPU(cpu_id=2, bit_width=64, bus=bus)

    # Simulate runtime hierarchy configuration
    cpu1.set_hierarchy(0x10)   # e.g. AHB Master 0
    cpu2.set_hierarchy(0x20)   # e.g. AXI Master 1

    print(f"Initial state: {cpu1}")
    print(f"Initial state: {cpu2}\n")

    # Normal execution
    for _ in range(3):
        cpu1.step()
        cpu2.step()

    print(f"After normal steps: {cpu1}")
    print(f"After normal steps: {cpu2}\n")

    # Console-style control simulation
    print("--- Console Control Simulation ---")
    cpu1.stall()
    print(f"After stall: {cpu1}")

    cpu1.resume()
    print(f"After resume: {cpu1}\n")

    # Enter dummy mode (used during hang recovery)
    cpu2.enter_dummy_mode()
    print(f"After entering dummy mode: {cpu2}")
    cpu2.exit_dummy_mode()

    print("\n=== Demo Finished ===")


if __name__ == "__main__":
    main()