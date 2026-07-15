"""SSOT symbolic SoC address map for campaign generators."""

from __future__ import annotations

SYM_ADDR: dict[str, int] = {
    "SFR_CTRL": 0x40000000,
    "SFR_CFG": 0x40000004,
    "SFR_CLK": 0x40000008,
    "SFR_INT_EN": 0x4000000C,
    "SFR_DMA_SRC": 0x40000010,
    "SFR_DMA_DST": 0x40000014,
    "SFR_STATUS": 0x40000018,
    "SFR_GPIO_DIR": 0x4000001C,
    "SFR_GPIO_OUT": 0x40000020,
    "SFR_GPIO_IN": 0x40000024,
    "SFR_WDT": 0x40000028,
    "SFR_VERSION": 0x4000002C,
    "SFR_XZ_PORT": 0x400000FC,
    "SRAM_MARKER": 0x80000000,
    "SRAM_AUX": 0x80000004,
    "UART_BAUD": 0xC0000000,
    "UART_IRQ_HANG": 0xC0000010,
}


def resolve_addr(token: str) -> int:
    token = token.strip()
    if token in SYM_ADDR:
        return SYM_ADDR[token]
    return int(token, 0)