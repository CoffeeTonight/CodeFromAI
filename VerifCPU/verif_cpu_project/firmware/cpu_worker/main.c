#include "common/verif_cpu.h"

int main(void)
{
    vtrace_enter(200);

    // Worker role example
    volatile uint32_t counter = 0;
    for (int i = 0; i < 100; i++) {
        counter++;
    }

    vtrace_exit(200);
    vstop();
    return 0;
}