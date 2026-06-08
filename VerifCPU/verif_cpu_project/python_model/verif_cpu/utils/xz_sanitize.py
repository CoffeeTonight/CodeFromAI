"""X/Z detection — any contaminated bit → 0xDEADDEAD + warning log."""

XZ_DEAD_PATTERN = 0xDEADDEAD


def dead_value(bit_width: int = 32) -> int:
    mask = (1 << bit_width) - 1
    return XZ_DEAD_PATTERN & mask


def has_xz(xz_mask: int) -> bool:
    """True when any bit in the word is X or Z (tracked via per-bit xz_mask)."""
    return xz_mask != 0


def sanitize_if_xz(cpu, value: int, xz_mask: int, bit_width: int, context: str) -> int:
    """
    If xz_mask is non-zero, log a warning on cpu and return 0xDEADDEAD.
    Otherwise return value masked to bit_width.
    """
    mask = (1 << bit_width) - 1
    if not has_xz(xz_mask):
        return value & mask

    hex_w = max(4, (bit_width + 3) // 4)
    msg = (
        f"[WARN] X/Z detected at {context} "
        f"(raw=0x{value & mask:0{hex_w}x}, xz_mask=0x{xz_mask:0{hex_w}x}) "
        f"— replaced with 0x{dead_value(bit_width):08x}"
    )

    if hasattr(cpu, "log"):
        cpu.log(msg)
    elif getattr(cpu, "trace_enabled", True):
        print(f"SCPU{cpu.cpu_id} > {msg}")

    if hasattr(cpu, "xz_warn_count"):
        cpu.xz_warn_count += 1

    return dead_value(bit_width)