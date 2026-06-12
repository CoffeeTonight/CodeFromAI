"""
VerifCPU High-Fidelity Tracing Demo (New Major Feature)

This demo showcases the new rich instruction tracing system:

- Register before/after deltas on every step
- Structured StepRecord objects
- Easy querying of recent execution
- Clean pretty-print output
- Works together with existing WDT, bus, function tracing, etc.

This is the kind of observability that makes the Python model extremely powerful
as a verification golden model / debug aid.
"""

from verif_cpu.core.cpu import VerifCPU
from verif_cpu.memory.unified_pool import UnifiedFirmwarePool
from verif_cpu.bus.simple_bus import SimpleMemoryBus
from verif_cpu.tracing.instruction_tracer import InstructionTracer, RegChange


def build_small_firmware() -> bytes:
    """Simple firmware with ALU + load/store activity"""
    import struct
    from verif_cpu.core.isa import encode_addi, encode_add, encode_sw, encode_lw

    words = []
    words.append(encode_addi(1, 0, 0x1000))      # base
    words.append(encode_addi(2, 0, 0xDEAD))
    words.append(encode_addi(3, 0, 0xBEEF))
    words.append(encode_add(4, 2, 3))            # x4 = 0xDEAD + 0xBEEF
    words.append(encode_sw(4, 1, 0))             # store to 0x1000
    words.append(encode_lw(5, 1, 0))             # load back
    words.append(encode_addi(6, 5, 1))
    words.append(encode_addi(0, 0, 0))           # nop
    return struct.pack("<" + "I" * len(words), *words)


def main():
    print("=" * 80)
    print("VerifCPU High-Fidelity Instruction Tracing Demo")
    print("=" * 80)

    bus = SimpleMemoryBus(0x10000)

    fw = build_small_firmware()
    with open("/tmp/rich_trace_fw.bin", "wb") as f:
        f.write(fw)

    pool = UnifiedFirmwarePool()
    pool.load_from_file("/tmp/rich_trace_fw.bin")
    pool.assign_region(1, 0, len(fw))

    cpu = VerifCPU(1, 32, bus=bus)
    cpu.attach_firmware(pool, 0, len(fw))

    # Attach the rich tracer for automatic high-fidelity recording
    rich_tracer = InstructionTracer(cpu_id=1, max_steps=256)
    cpu.attach_instruction_tracer(rich_tracer)

    print("\n--- Running CPU with automatic rich tracing (via clean hook) ---\n")

    for _ in range(10):
        cpu.step()

    print("\n--- Rich Trace (last 10 steps with register deltas) ---")
    rich_tracer.pretty_print_last(10)

    print("\n--- Query: Steps that modified x4 ---")
    for rec in rich_tracer.get_last_steps(20):
        if 4 in rec.reg_changes:
            print(f"  Cycle {rec.cycle}: {rec.disasm}  x4 changed")

    print("\nDemo complete. Rich tracing now works automatically via CPU.step().")


if __name__ == "__main__":
    main()
