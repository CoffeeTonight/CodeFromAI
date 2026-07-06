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

#define CAMPAIGN_MAX_SLOTS     60
#define MANIFEST_SLAVE_COUNT   60
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
    { "RES04", 4, 3, POOL_WORD_SLOT3, 0, 0, "axi4lite", "S04_AXI" },
    { "RES05", 5, 4, POOL_WORD_SLOT4, 0, 0, "axi4lite", "S05_AXI" },
    { "RES06", 6, 5, POOL_WORD_SLOT5, 0, 0, "axi4lite", "S06_AXI" },
    { "RES07", 7, 6, POOL_WORD_SLOT6, 0, 0, "axi4lite", "S07_AXI" },
    { "RES08", 8, 7, POOL_WORD_SLOT7, 0, 0, "axi4lite", "S08_AXI" },
    { "RES09", 9, 8, POOL_WORD_SLOT8, 0, 0, "axi4lite", "S09_AXI" },
    { "RES10", 10, 9, POOL_WORD_SLOT9, 0, 0, "axi4lite", "S10_AXI" },
    { "RES11", 11, 10, POOL_WORD_SLOT10, 0, 0, "axi4lite", "S11_AXI" },
    { "RES12", 12, 11, POOL_WORD_SLOT11, 0, 0, "axi4lite", "S12_AXI" },
    { "RES13", 13, 12, POOL_WORD_SLOT12, 0, 0, "axi4lite", "S13_AXI" },
    { "RES14", 14, 13, POOL_WORD_SLOT13, 0, 0, "axi4lite", "S14_AXI" },
    { "RES15", 15, 14, POOL_WORD_SLOT14, 0, 0, "axi4lite", "S15_AXI" },
    { "RES16", 16, 15, POOL_WORD_SLOT15, 0, 0, "axi4lite", "S16_AXI" },
    { "RES17", 17, 16, POOL_WORD_SLOT16, 0, 0, "axi4lite", "S17_AXI" },
    { "RES18", 18, 17, POOL_WORD_SLOT17, 0, 0, "axi4lite", "S18_AXI" },
    { "RES19", 19, 18, POOL_WORD_SLOT18, 0, 0, "axi4lite", "S19_AXI" },
    { "RES20", 20, 19, POOL_WORD_SLOT19, 0, 0, "axi4lite", "S20_AXI" },
    { "RES21", 21, 20, POOL_WORD_SLOT20, 0, 0, "axi4lite", "S21_AXI" },
    { "RES22", 22, 21, POOL_WORD_SLOT21, 0, 0, "axi4lite", "S22_AXI" },
    { "RES23", 23, 22, POOL_WORD_SLOT22, 0, 0, "axi4lite", "S23_AXI" },
    { "RES24", 24, 23, POOL_WORD_SLOT23, 0, 0, "axi4lite", "S24_AXI" },
    { "RES25", 25, 24, POOL_WORD_SLOT24, 0, 0, "axi4lite", "S25_AXI" },
    { "RES26", 26, 25, POOL_WORD_SLOT25, 0, 0, "axi4lite", "S26_AXI" },
    { "RES27", 27, 26, POOL_WORD_SLOT26, 0, 0, "axi4lite", "S27_AXI" },
    { "RES28", 28, 27, POOL_WORD_SLOT27, 0, 0, "axi4lite", "S28_AXI" },
    { "RES29", 29, 28, POOL_WORD_SLOT28, 0, 0, "axi4lite", "S29_AXI" },
    { "RES30", 30, 29, POOL_WORD_SLOT29, 0, 0, "axi4lite", "S30_AXI" },
    { "RES31", 31, 30, POOL_WORD_SLOT30, 0, 0, "axi4lite", "S31_AXI" },
    { "RES32", 32, 31, POOL_WORD_SLOT31, 0, 0, "axi4lite", "S32_AXI" },
    { "RES33", 33, 32, POOL_WORD_SLOT32, 0, 0, "axi4lite", "S33_AXI" },
    { "RES34", 34, 33, POOL_WORD_SLOT33, 0, 0, "axi4lite", "S34_AXI" },
    { "RES35", 35, 34, POOL_WORD_SLOT34, 0, 0, "axi4lite", "S35_AXI" },
    { "RES36", 36, 35, POOL_WORD_SLOT35, 0, 0, "axi4lite", "S36_AXI" },
    { "RES37", 37, 36, POOL_WORD_SLOT36, 0, 0, "axi4lite", "S37_AXI" },
    { "RES38", 38, 37, POOL_WORD_SLOT37, 0, 0, "axi4lite", "S38_AXI" },
    { "RES39", 39, 38, POOL_WORD_SLOT38, 0, 0, "axi4lite", "S39_AXI" },
    { "RES40", 40, 39, POOL_WORD_SLOT39, 0, 0, "axi4lite", "S40_AXI" },
    { "RES41", 41, 40, POOL_WORD_SLOT40, 0, 0, "axi4lite", "S41_AXI" },
    { "RES42", 42, 41, POOL_WORD_SLOT41, 0, 0, "axi4lite", "S42_AXI" },
    { "RES43", 43, 42, POOL_WORD_SLOT42, 0, 0, "axi4lite", "S43_AXI" },
    { "RES44", 44, 43, POOL_WORD_SLOT43, 0, 0, "axi4lite", "S44_AXI" },
    { "RES45", 45, 44, POOL_WORD_SLOT44, 0, 0, "axi4lite", "S45_AXI" },
    { "RES46", 46, 45, POOL_WORD_SLOT45, 0, 0, "axi4lite", "S46_AXI" },
    { "RES47", 47, 46, POOL_WORD_SLOT46, 0, 0, "axi4lite", "S47_AXI" },
    { "RES48", 48, 47, POOL_WORD_SLOT47, 0, 0, "axi4lite", "S48_AXI" },
    { "RES49", 49, 48, POOL_WORD_SLOT48, 0, 0, "axi4lite", "S49_AXI" },
    { "RES50", 50, 49, POOL_WORD_SLOT49, 0, 0, "axi4lite", "S50_AXI" },
    { "RES51", 51, 50, POOL_WORD_SLOT50, 0, 0, "axi4lite", "S51_AXI" },
    { "RES52", 52, 51, POOL_WORD_SLOT51, 0, 0, "axi4lite", "S52_AXI" },
    { "RES53", 53, 52, POOL_WORD_SLOT52, 0, 0, "axi4lite", "S53_AXI" },
    { "RES54", 54, 53, POOL_WORD_SLOT53, 0, 0, "axi4lite", "S54_AXI" },
    { "RES55", 55, 54, POOL_WORD_SLOT54, 0, 0, "axi4lite", "S55_AXI" },
    { "RES56", 56, 55, POOL_WORD_SLOT55, 0, 0, "axi4lite", "S56_AXI" },
    { "RES57", 57, 56, POOL_WORD_SLOT56, 0, 0, "axi4lite", "S57_AXI" },
    { "RES58", 58, 57, POOL_WORD_SLOT57, 0, 0, "axi4lite", "S58_AXI" },
    { "RES59", 59, 58, POOL_WORD_SLOT58, 0, 0, "ahb_lite", "M59_AHB" },
    { "RES60", 60, 59, POOL_WORD_SLOT59, 0, 0, "apb3", "S60_APB" },
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
