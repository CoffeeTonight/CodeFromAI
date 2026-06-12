#include "campaign_layout.h"
#include "soc_regs.h"
#include "verif_insns.h"

__attribute__((section(".phase_a.entry"), used))
void phase_a_entry(void)
{
    vtrace_enter(0xA0);
    rv_addi(1, 0, 500);
    vwdt_set_rs1(1);
    load_soc_addr(10, SFR_CTRL);
    rv_addi(11, 0, 1);
    rv_sw(11, 10, 0);
    vtrace_log(0xA1);
    vtrace_exit(0xA0);
    vstop();
}