#include "campaign_layout.h"
#include "soc_regs.h"
#include "verif_insns.h"

__attribute__((section(".phase_c.entry"), used))
void phase_c_entry(void)
{
    vtrace_enter(0xC0);
    rv_addi(1, 0, -1096);
    vwdt_set_rs1(1);
    vwave(1, 0);
    vwave(3, 0x10);
    vwave(2, 0);
    rv_addi(20, 0, 1);
    rv_addi(21, 0, 0x55);
    vforce(20, 21);
    vrelease(20);
    vdummy_on();
    rv_addi(1, 0, 0x11);
    rv_addi(2, 0, 0x22);
    rv_add(3, 1, 2);
    rv_sub(4, 2, 1);
    rv_and(5, 1, 2);
    rv_or(6, 1, 2);
    rv_xor(7, 1, 2);
    rv_andi(8, 1, 0xF);
    rv_ori(9, 1, 0xF);
    rv_auipc(15, 0);
    rv_addi(12, 0, 1);
    rv_addi(13, 0, 1);
    rv_beq(12, 13, 8);
    rv_addi(16, 0, 0xAB);
    load_soc_addr(10, SFR_CTRL);
    rv_lw(11, 10, 0);
    rv_lui(12, 0xDEADE);
    rv_addi(12, 12, -339);
    rv_xor(13, 11, 12);
    rv_addi(1, 0, 1);
    rv_beq(13, 0, 8);
    rv_addi(1, 0, 0);
    vassert_id(40);
    vdummy_off();
    load_soc_addr(10, SFR_CTRL);
    rv_addi(14, 0, 0x10);
    rv_lui(16, 0x5);
    vhw_force(10, 14, 16);
    rv_lw(11, 10, 0);
    rv_lui(12, 0x5);
    rv_xor(13, 11, 12);
    rv_addi(1, 0, 1);
    rv_beq(13, 0, 8);
    rv_addi(1, 0, 0);
    vassert_id(43);
    vhw_release(10, 14);
    rv_lw(11, 10, 0);
    rv_addi(1, 0, 1);
    vassert_id(41);
    load_soc_addr(10, SFR_XZ_PORT);
    rv_lw(11, 10, 0);
    rv_lui(12, 0xDEADE);
    rv_addi(12, 12, -339);
    rv_xor(13, 11, 12);
    rv_addi(1, 0, 1);
    rv_beq(13, 0, 8);
    rv_addi(1, 0, 0);
    vassert_id(42);
    vwdt_pet();
    vsync(1);
    vtrace_log(0xC2);
    vwave(0, 0);
    vtrace_exit(0xC0);
    vstop();
}