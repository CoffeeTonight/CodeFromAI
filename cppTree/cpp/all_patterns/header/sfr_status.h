// sfr_status.h
#ifndef SFR_STATUS_H
#define SFR_STATUS_H

#include "sfr_base.h"

typedef struct {
    struct {
        uint32_t ready : 1;
    } bits;
    uint32_t reg;
} StatusReg;

#endif
