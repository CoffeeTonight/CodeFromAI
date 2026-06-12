#ifndef CAMPAIGN_MANIFEST_H
#define CAMPAIGN_MANIFEST_H

#include <stdint.h>
#include "soc_regs.h"
#include "campaign_layout.h"

/*
 * Campaign verification manifest — SINGLE SOURCE OF TRUTH
 *
 * Master CPU reads this table in Phase B and injects bus_read hints
 * per slave (tap). Each slave Agent collects only its tap's txns into
 * slots; Phase C icode uses the same addr/expect/icode binding.
 *
 * Edit ONLY this file (then: make soc_init manifest).
 */

#define MANIFEST_SLAVE_COUNT 3

typedef struct {
    const char *name;
    uint8_t     cpu_id;
    uint8_t     tap_port;
    uint32_t    pool_word;
    uint8_t     target_count;
} manifest_slave_t;

typedef struct {
    uint32_t    bus_addr;
    uint32_t    expect;
    const char *icode;
} manifest_target_t;

static const manifest_slave_t MANIFEST_SLAVES[MANIFEST_SLAVE_COUNT] = {
    { "SFR",  1, 0, POOL_WORD_CPU1, 2 },
    { "SRAM", 2, 1, POOL_WORD_CPU2, 2 },
    { "UART", 3, 2, POOL_WORD_CPU3, 2 },
};

static const manifest_target_t MANIFEST_SFR_TARGETS[] = {
    { SFR_CTRL,     0x00000001u, "check_sfr_ctrl"  },
    { SFR_CFG,      0x000000FFu, "check_sfr_mask"  },
};

static const manifest_target_t MANIFEST_SRAM_TARGETS[] = {
    { SRAM_MARKER,  0xDEADBEEFu, "check_sram_marker" },
    { SRAM_AUX,     0xCAFEBABEu, "check_sram_aux"    },
};

static const manifest_target_t MANIFEST_UART_TARGETS[] = {
    { UART_BAUD,    0x00000080u, "check_uart_baud" },
    { UART_IRQ_HANG, 0xDEADDEADu, "check_uart_irq" },
};

#endif