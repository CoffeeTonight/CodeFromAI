#ifndef GPIO_REGISTERS_H
#define GPIO_REGISTERS_H

#include <stdint.h>

typedef struct {
    struct {
        uint32_t input : 1;
        uint32_t output : 1;
    } bits;
    uint32_t value;
} GpioRegs;

static GpioRegs* gpio = (GpioRegs*)0x60000000;

#endif