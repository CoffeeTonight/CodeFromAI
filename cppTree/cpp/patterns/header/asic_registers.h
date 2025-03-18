// asic_registers.h
#ifndef ASIC_REGISTERS_H
#define ASIC_REGISTERS_H

#include <stdint.h>

#define ASIC_BASE ((volatile uint32_t*)0xA0000000)

// 데이터 전송 제어 SFR 그룹
typedef struct {
    struct {
        uint32_t start : 1;  // 전송 시작
        uint32_t mode  : 2;  // 모드 선택 (0: read, 1: write)
    } bits;
    uint32_t reg;
} ControlReg;

typedef struct {
    uint32_t reg;  // 데이터 버퍼
} DataReg;

typedef struct {
    struct {
        uint32_t ready : 1;  // 준비 상태
    } bits;
    uint32_t reg;
} StatusReg;

typedef struct {
    ControlReg ctrl;
    DataReg    data;
    StatusReg  status;
} AsicTransferReg;

static AsicTransferReg* asic = (AsicTransferReg*)ASIC_BASE;

#endif
