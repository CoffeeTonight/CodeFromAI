#ifndef CAMPAIGN_LAYOUT_H
#define CAMPAIGN_LAYOUT_H

/* Firmware entry offsets within each 8 KiB CPU region — must match tb_full_campaign.v */
#define OFF_PHASE_A       0x000u
#define OFF_PHASE_B       0x100u
#define OFF_PHASE_C       0x200u
#define OFF_UART_HANG     0xC00u
#define OFF_UART_RECOVER  0xD00u

#define REGION_SIZE       0x2000u

/* Unified pool placement (word index in full_campaign_unified.hex) */
#define POOL_WORD_CPU1    0x0000u
#define POOL_WORD_CPU2    0x4000u
#define POOL_WORD_CPU3    0x8000u
#define POOL_WORD_ICODE   0xC000u

#endif