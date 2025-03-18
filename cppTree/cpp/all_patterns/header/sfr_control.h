// sfr_control.h
#ifndef SFR_CONTROL_H
#define SFR_CONTROL_H

#include "sfr_base.h"  // sfr_base.h 호출

typedef struct {
    struct {
        uint32_t start : 1;
        uint32_t mode  : 2;
    } bits;
    uint32_t reg;
} ControlReg;

#endif
