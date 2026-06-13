#include "campaign_layout.h"
#include "soc_regs.h"
#include "verif_insns.h"

__attribute__((section(".sync_barrier.entry"), used))
void sync_barrier_entry(void)
{
    vtrace_enter(0xF1);
    vsync(CAMPAIGN_SYNC_BARRIER_ID);
    load_soc_addr(10, SRAM_MARKER);
    rv_lw(11, 10, 0);
    rv_addi(1, 0, 1);
    vassert_id(51);
    vtrace_exit(0xF1);
    vstop();
}