#ifndef CAMPAIGN_LAYOUT_H
#define CAMPAIGN_LAYOUT_H

/* Auto-generated from campaign_slots.yaml */

#define OFF_PHASE_A       0x000u
#define OFF_PHASE_B       0x100u
#define OFF_PHASE_C       0x200u
#define OFF_SYNC_BARRIER  0x380u
#define OFF_UART_HANG     0xC00u
#define OFF_UART_RECOVER  0xD00u

#define CAMPAIGN_SYNC_BARRIER_ID  10u

#define REGION_SIZE       0x2000u
#define POOL_WORD_STRIDE  0x0800u
#define POOL_WORD_MASTER  0x0000u

#define POOL_WORD_SLOT0  0x0000u
#define POOL_WORD_SLOT1  0x0800u
#define POOL_WORD_SLOT2  0x1000u
#define POOL_WORD_ICODE   0x1800u

#endif
