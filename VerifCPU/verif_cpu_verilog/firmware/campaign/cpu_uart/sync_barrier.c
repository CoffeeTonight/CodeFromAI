#include "campaign_layout.h"
#include "soc_regs.h"
#include "verif_insns.h"

__attribute__((section(".sync_barrier.entry"), used))
void sync_barrier_entry(void)
{
    vtrace_enter(0xF2);
    vsync(CAMPAIGN_SYNC_BARRIER_ID);
    load_soc_addr(10, UART_BAUD);
    rv_lw(11, 10, 0);
    /* Assert loaded bus value, not hard-coded 1 */
    vassert_rs1(11, 52);
    vtrace_exit(0xF2);
    vstop();
}