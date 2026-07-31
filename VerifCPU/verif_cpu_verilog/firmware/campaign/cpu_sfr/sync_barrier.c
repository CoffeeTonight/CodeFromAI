#include "campaign_layout.h"
#include "soc_regs.h"
#include "verif_insns.h"

/* Exact compare: load vs expected → xor; beq equal skip fail; vassert_rs1 */
__attribute__((section(".sync_barrier.entry"), used))
void sync_barrier_entry(void)
{
    vtrace_enter(0xF0);
    vsync(CAMPAIGN_SYNC_BARRIER_ID);
    load_soc_addr(10, SFR_CTRL);
    rv_lw(11, 10, 0);            /* actual */
    rv_addi(12, 0, 1);           /* expected SFR_CTRL after soc_init */
    rv_addi(1, 0, 1);            /* assume PASS */
    rv_xor(13, 11, 12);          /* 0 iff exact match */
    rv_beq(13, 0, 8);            /* equal → skip fail (PC+8) */
    rv_addi(1, 0, 0);            /* mismatch → FAIL */
    vassert_rs1(1, 50);
    vtrace_exit(0xF0);
    vstop();
}
