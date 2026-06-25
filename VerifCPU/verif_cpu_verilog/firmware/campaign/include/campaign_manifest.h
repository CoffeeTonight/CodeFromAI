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

#define CAMPAIGN_MAX_SLOTS     0
#define MANIFEST_SLAVE_COUNT   0
#define CAMPAIGN_MASTER_PRESENT 1

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
};

static const manifest_master_t MANIFEST_MASTER = {
    "MSTR", 0, 0, POOL_WORD_MASTER, 2, 1, "axi4lite", "S00_AXI",
};

static const manifest_target_t MANIFEST_MSTR_TARGETS[] = {
    { SFR_CTRL, 0x00000001u, "check_sfr_ctrl" },
    { SFR_CFG, 0x000000FFu, "check_sfr_mask" },
};

#endif
