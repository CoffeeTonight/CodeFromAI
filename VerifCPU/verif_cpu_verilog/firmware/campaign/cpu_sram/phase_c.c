#include "campaign_layout.h"
#include "soc_regs.h"
#include "verif_insns.h"

__attribute__((section(".phase_c.entry"), used))
void phase_c_entry(void)
{
    vtrace_enter(0xD0);
    load_soc_addr(10, SRAM_MARKER);
    rv_lw(11, 10, 0);
    rv_lui(12, 0xDEADB);
    rv_ori(12, 12, 0xEEF);
    rv_xor(13, 11, 12);
    rv_addi(1, 0, 1);
    rv_beq(13, 0, 8);
    rv_addi(1, 0, 0);
    vassert_id(21);
    vsync(2);
    rv_jal(15, 8);
    rv_addi(14, 0, 0xBAD);
    rv_addi(17, 0, 0xCD);
    rv_addi(1, 0, 0x244);  /* OFF_PHASE_C + jalr target (matches Python layout) */
    rv_jalr(16, 1, 0);
    rv_addi(18, 0, 0xEF);
    vtrace_exit(0xD0);
    vstop();
}