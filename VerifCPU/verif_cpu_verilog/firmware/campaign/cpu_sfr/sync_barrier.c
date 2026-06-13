#include "campaign_layout.h"
#include "soc_regs.h"
#include "verif_insns.h"

__attribute__((section(".sync_barrier.entry"), used))
void sync_barrier_entry(void)
{
    vtrace_enter(0xF0);
    vsync(CAMPAIGN_SYNC_BARRIER_ID);
    load_soc_addr(10, SFR_CTRL);
    rv_lw(11, 10, 0);
    rv_addi(1, 0, 1);
    vassert_id(50);
    vtrace_exit(0xF0);
    vstop();
}