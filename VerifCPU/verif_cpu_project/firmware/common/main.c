#include <stdio.h>
#include "verif_cpu.h"

// This is the reference main framework.
// Only the role_work() function is expected to be different per role.

__attribute__((weak)) void role_work(void)
{
    // Default empty role - override in role-specific main.c
    printf("[CPU] Default role_work() - doing nothing\n");
}

int main(void)
{
    printf("[CPU%d] Firmware started\n", CPU_ID);

    // Common initialization for all CPUs
    // (tracing setup, WDT pet initial, etc. can go here)

    // Call the role-specific function
    role_work();

    // Safe termination for verification CPUs
    printf("[CPU%d] Firmware Done. Entering stall...\n", CPU_ID);
    cpu_stall();   // You should define or implement cpu_stall() appropriately

    return 0;
}