#include "campaign_layout.h"
#include "soc_regs.h"
#include "verif_insns.h"

__attribute__((section(".uart_hang.entry"), used))
void uart_hang_entry(void)
{
    rv_addi(1, 0, 8);
    vwdt_set_rs1(1);
    rv_addi(2, 0, 0);
    rv_addi(2, 2, 1); rv_addi(2, 2, 1); rv_addi(2, 2, 1); rv_addi(2, 2, 1);
    rv_addi(2, 2, 1); rv_addi(2, 2, 1); rv_addi(2, 2, 1); rv_addi(2, 2, 1);
    rv_addi(2, 2, 1); rv_addi(2, 2, 1); rv_addi(2, 2, 1); rv_addi(2, 2, 1);
    rv_addi(2, 2, 1); rv_addi(2, 2, 1); rv_addi(2, 2, 1); rv_addi(2, 2, 1);
    rv_addi(2, 2, 1); rv_addi(2, 2, 1); rv_addi(2, 2, 1); rv_addi(2, 2, 1);
    rv_addi(2, 2, 1); rv_addi(2, 2, 1); rv_addi(2, 2, 1); rv_addi(2, 2, 1);
    rv_addi(2, 2, 1); rv_addi(2, 2, 1); rv_addi(2, 2, 1); rv_addi(2, 2, 1);
    rv_addi(2, 2, 1); rv_addi(2, 2, 1); rv_addi(2, 2, 1); rv_addi(2, 2, 1);
    rv_addi(2, 2, 1); rv_addi(2, 2, 1); rv_addi(2, 2, 1); rv_addi(2, 2, 1);
    rv_addi(2, 2, 1); rv_addi(2, 2, 1); rv_addi(2, 2, 1); rv_addi(2, 2, 1);
    vstop();
}

__attribute__((section(".uart_recover.entry"), used))
void uart_recover_entry(void)
{
    vwdt_pet();
    vtrace_enter(0xE0);
    load_soc_addr(10, UART_IRQ_HANG);
    rv_lw(11, 10, 0);
    rv_lui(12, 0xDEADE);
    rv_addi(12, 12, -339);
    rv_xor(13, 11, 12);
    rv_addi(1, 0, 1);
    rv_beq(13, 0, 8);
    rv_addi(1, 0, 0);
    vassert_id(30);
    vdummy_off();
    vsync(3);
    vtrace_exit(0xE0);
    vstop();
}