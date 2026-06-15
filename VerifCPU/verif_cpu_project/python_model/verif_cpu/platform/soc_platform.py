"""Auto-generated from firmware/campaign/include/soc_platform.h."""

INIT_DONE_ADDR = 0x40000018
INIT_DONE_MASK = 0x80000000
INIT_DONE_VALUE = 0x80000000
INIT_DONE_POLL_MAX = 4096


def init_done_met(val: int) -> bool:
    return (val & INIT_DONE_MASK) == INIT_DONE_VALUE
