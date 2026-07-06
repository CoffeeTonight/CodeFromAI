#ifndef SOC_INIT_SEQ_H
#define SOC_INIT_SEQ_H

#include <stdint.h>
#include "soc_regs.h"
#include "soc_platform.h"

/* Single source of truth for SoC boot — 12 SFR R/W + peripheral markers */

#define SOC_INIT_OP_WRITE 0u
#define SOC_INIT_OP_READ  1u

typedef struct {
    uint8_t  op;
    uint32_t addr;
    uint32_t wdata;
    uint32_t expect;
} soc_init_step_t;

#define SOC_INIT_STEP_COUNT 19

static const soc_init_step_t SOC_INIT_STEPS[SOC_INIT_STEP_COUNT] = {
    /* --- 12 SFR-centric steps (realistic bring-up) --- */
    { SOC_INIT_OP_WRITE, SFR_CTRL,     0x00000001u, 0u },
    { SOC_INIT_OP_WRITE, SFR_CFG,      0x000000FFu, 0u },
    { SOC_INIT_OP_WRITE, SFR_CLK,      0x00000010u, 0u },
    { SOC_INIT_OP_READ,  SFR_CTRL,     0u,          0x00000001u },
    { SOC_INIT_OP_WRITE, SFR_INT_EN,   0x00000003u, 0u },
    { SOC_INIT_OP_WRITE, SFR_DMA_SRC,  0x80000000u, 0u },
    { SOC_INIT_OP_WRITE, SFR_DMA_DST,  0x80001000u, 0u },
    { SOC_INIT_OP_WRITE, SFR_STATUS,   0x00000000u, 0u },
    { SOC_INIT_OP_READ,  SFR_CFG,      0u,          0x000000FFu },
    { SOC_INIT_OP_WRITE, SFR_GPIO_DIR, 0x0000FFFFu, 0u },
    { SOC_INIT_OP_WRITE, SFR_GPIO_OUT, 0x0000CAFEu, 0u },
    { SOC_INIT_OP_READ,  SFR_GPIO_OUT, 0u,          0x0000CAFEu },
    /* --- SRAM / UART markers (icode + campaign checks) --- */
    { SOC_INIT_OP_WRITE, SRAM_MARKER,  0xDEADBEEFu, 0u },
    { SOC_INIT_OP_WRITE, SRAM_AUX,     0xCAFEBABEu, 0u },
    { SOC_INIT_OP_WRITE, UART_BAUD,     0x00000080u, 0u },
    { SOC_INIT_OP_WRITE, UART_IRQ_HANG, 0xDEADDEADu, 0u },
    { SOC_INIT_OP_READ,  UART_BAUD,     0u,          0x00000080u },
    { SOC_INIT_OP_READ,  UART_IRQ_HANG, 0u,          0xDEADDEADu },
    /* --- Master polls SFR_STATUS bit31 — keep wdata in sync with soc_platform.h --- */
    { SOC_INIT_OP_WRITE, SFR_STATUS,     SOC_INIT_DONE_VALUE, 0u },
};

#endif