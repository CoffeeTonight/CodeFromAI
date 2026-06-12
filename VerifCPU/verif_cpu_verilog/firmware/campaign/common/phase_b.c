#include "campaign_layout.h"
#include "soc_regs.h"
#include "verif_insns.h"

__attribute__((section(".phase_b.entry"), used))
void phase_b_entry(void)
{
    vtrace_enter(0xB0);
    load_soc_addr(10, SFR_CTRL);
    rv_lw(11, 10, 0);
    vtrace_log(0xB1);
    vtrace_exit(0xB0);
    vstop();
}