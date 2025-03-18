#ifndef TIMER_REGISTERS_H
#define TIMER_REGISTERS_H

#include <stdint.h>

#define TIMER_BASE ((volatile uint32_t*)0x50000000)

typedef struct {
    struct {
        uint32_t start : 1;
        uint32_t stop : 1;
    } bits;
    uint32_t count;
} TimerRegs;

#endif