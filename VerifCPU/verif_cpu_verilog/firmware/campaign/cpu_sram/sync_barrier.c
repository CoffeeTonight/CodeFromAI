#include "campaign_layout.h"
#include "soc_regs.h"
#include "verif_insns.h"

/* Exact compare: load vs expected → xor; beq equal skip fail; vassert_rs1 */
__attribute__((section(".sync_barrier.entry"), used))
void sync_barrier_entry(void)
{
    vtrace_enter(0xF1);
    vsync(CAMPAIGN_SYNC_BARRIER_ID);
    load_soc_addr(10, SRAM_MARKER);
    rv_lw(11, 10, 0);            /* actual */
    load_soc_addr(12, 0xDEADBEEFu); /* expected after soc_init */
    rv_addi(1, 0, 1);            /* assume PASS */
    rv_xor(13, 11, 12);          /* 0 iff exact match */
    rv_beq(13, 0, 8);            /* equal → skip fail */
    rv_addi(1, 0, 0);            /* mismatch → FAIL */
    vassert_rs1(1, 51);
    vtrace_exit(0xF1);
    vstop();
}
