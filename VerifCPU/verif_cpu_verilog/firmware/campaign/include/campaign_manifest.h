#ifndef CAMPAIGN_MANIFEST_H
#define CAMPAIGN_MANIFEST_H

#include <stdint.h>
#include "soc_regs.h"
#include "campaign_layout.h"

/* Auto-generated from firmware/campaign/campaign_slots.yaml — do not edit */
/*
 * enabled=0 slots are RESERVED: hierarchy/AXI may be wired later.
 * Campaign TB does not step those VCPUs; agents see no tap traffic.
 * SCPU0 master targets: MANIFEST_MASTER (when master vcpu enabled).
 */

#define CAMPAIGN_MAX_SLOTS     3
#define MANIFEST_SLAVE_COUNT   3
#define CAMPAIGN_MASTER_PRESENT 0

typedef struct {
    const char *name;
    uint8_t     cpu_id;
    uint8_t     tap_port;
    uint32_t    pool_word;
    uint8_t     target_count;
    uint8_t     enabled;
    const char *bus_type;
    const char *bus_port;
} manifest_slave_t;

typedef struct {
    const char *name;
    uint8_t     cpu_id;
    uint8_t     tap_port;
    uint32_t    pool_word;
    uint8_t     target_count;
    uint8_t     enabled;
    const char *bus_type;
    const char *bus_port;
} manifest_master_t;

typedef struct {
    uint32_t    bus_addr;
    uint32_t    expect;
    const char *icode;
} manifest_target_t;

static const manifest_slave_t MANIFEST_SLAVES[MANIFEST_SLAVE_COUNT] = {
    { "SFR", 1, 0, POOL_WORD_SLOT0, 2, 1, "apb3", "S01_APB" },
    { "SRAM", 2, 1, POOL_WORD_SLOT1, 2, 1, "ahb_lite", "M02_AHB" },
    { "UART", 3, 2, POOL_WORD_SLOT2, 2, 1, "axi4lite", "S03_AXI" },
};

static const manifest_target_t MANIFEST_SFR_TARGETS[] = {
    { SFR_CTRL, 0x00000001u, "check_sfr_ctrl" },
    { SFR_CFG, 0x000000FFu, "check_sfr_mask" },
};

static const manifest_target_t MANIFEST_SRAM_TARGETS[] = {
    { SRAM_MARKER, 0xDEADBEEFu, "check_sram_marker" },
    { SRAM_AUX, 0xCAFEBABEu, "check_sram_aux" },
};

static const manifest_target_t MANIFEST_UART_TARGETS[] = {
    { UART_BAUD, 0x00000080u, "check_uart_baud" },
    { UART_IRQ_HANG, 0xDEADDEADu, "check_uart_irq" },
};

#endif
