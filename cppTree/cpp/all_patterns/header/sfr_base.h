// sfr_base.h
#ifndef SFR_BASE_H
#define SFR_BASE_H

#include <stdint.h>

#ifndef ASIC_BASE_ADDR  // Makefile 환경 변수로 재정의 가능
#define ASIC_BASE_ADDR 0xA0000000
#endif

#define ASIC_BASE ((volatile uint32_t*)ASIC_BASE_ADDR)

typedef struct {
    uint32_t data;
} DataReg;

#endif
