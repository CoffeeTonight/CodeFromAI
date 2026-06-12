"""Shared policy: embed icode via readmemh vs lazy file-backed pool."""

POOL_READMEMH_MAX_BYTES = 0x40000  # 256 KiB — icode pool <= this merges into unified hex
POOL_WORD_ICODE = 0xC000
VCPU_IMAGE_BYTES = 0x22000


def icode_use_lazy(pool_bytes: int) -> bool:
    return pool_bytes > POOL_READMEMH_MAX_BYTES


def unified_image_bytes(pool_bytes: int) -> int:
    icode_end = POOL_WORD_ICODE * 4 + pool_bytes
    return max(VCPU_IMAGE_BYTES, icode_end)


def unified_mem_words(pool_bytes: int) -> int:
    total = unified_image_bytes(pool_bytes)
    words = (total + 3) // 4
    return (words + 0xFFF) & ~0xFFF