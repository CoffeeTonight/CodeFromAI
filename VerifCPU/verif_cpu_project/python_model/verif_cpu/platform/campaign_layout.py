"""Campaign pool layout — mirrors firmware/campaign/include/campaign_layout.h."""

OFF_PHASE_A = 0x000
OFF_PHASE_B = 0x100
OFF_PHASE_C = 0x200
OFF_UART_HANG = 0xC00
OFF_UART_RECOVER = 0xD00

REGION_SIZE = 0x2000

POOL_WORD_CPU1 = 0x0000
POOL_WORD_CPU2 = 0x4000
POOL_WORD_CPU3 = 0x8000
POOL_WORD_ICODE = 0xC000

VCPU_IMAGE_BYTES = 0x22000
POOL_READMEMH_MAX_BYTES = 0x40000  # 256 KiB — same as campaign_pool_policy.py


def pool_byte_base(pool_word: int) -> int:
    return pool_word * 4


CPU_POOL_WORD = {
    1: POOL_WORD_CPU1,
    2: POOL_WORD_CPU2,
    3: POOL_WORD_CPU3,
}