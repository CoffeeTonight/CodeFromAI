#ifndef SOC_PLATFORM_H
#define SOC_PLATFORM_H

#include "soc_regs.h"

/*
 * Per-SoC platform hooks — edit for each DUT memory map.
 * gen_soc_init.py emits Verilog macros (campaign_soc_platform.vh).
 *
 * Master agent polls INIT_DONE_ADDR until (read & MASK) == VALUE.
 */

#define SOC_INIT_DONE_ADDR   SFR_STATUS
#define SOC_INIT_DONE_MASK   0x80000000u
#define SOC_INIT_DONE_VALUE  0x80000000u

#endif