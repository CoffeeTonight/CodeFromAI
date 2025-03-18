#ifndef SFR_REGISTERS_H
#define SFR_REGISTERS_H

#include <stdint.h>

#define PERIPH_BASE ((volatile uint32_t*)0x40000000)

typedef struct {
    struct {
        uint32_t enable : 1;
        uint32_t data : 1;
    } bits;
    uint32_t reg;
} ControlReg;

typedef struct {
    uint32_t reg;
} DataReg;

typedef struct {
    struct {
        uint32_t status : 1;
    } bits;
    uint32_t reg;
} StatusReg;

typedef struct {
    ControlReg control;
    StatusReg status;
    DataReg data_in;
    DataReg data_out;
} PeripheralReg;

#endif