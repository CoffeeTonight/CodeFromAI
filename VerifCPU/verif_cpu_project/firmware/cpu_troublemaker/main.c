#include "common/verif_cpu.h"

int main(void)
{
    vtrace_enter(300);

    // This CPU is designed to trigger WDT (long loop without petting)
    volatile int x = 0;
    for (int i = 0; i < 10000; i++) {
        x += 1;
    }

    vtrace_exit(300);
    vstop();
    return 0;
}