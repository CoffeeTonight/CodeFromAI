#include "common/verif_cpu.h"

int main(void)
{
    vtrace_enter(1);

    // Do some verification work
    volatile int x = 0x1234;
    x += 1;

    vassert(x > 0);

    vtrace_exit(1);

    // Stop simulation from firmware
    vstop();

    return 0;
}