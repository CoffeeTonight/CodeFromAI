// src/testcase_bitmanipulation.cpp
#include <stdint.h>

// SFR 기본 주소 정의 (Makefile에서 재정의 가능)
#ifndef SFR_BASE_ADDR
#define SFR_BASE_ADDR 0xD0000000
#endif
#define SFR_BASE ((volatile uint32_t*)SFR_BASE_ADDR)

// SFR 레지스터 구조체 정의
typedef struct {
    uint32_t ctrl;
} SfrReg;

static SfrReg* sfr = (SfrReg*)SFR_BASE;

// 비트 조작 매크로
#define SET_BIT(reg, bit) ((reg) |= (1U << (bit)))
#define CLEAR_BIT(reg, bit) ((reg) &= ~(1U << (bit)))

int main() {
    SET_BIT(sfr->ctrl, 0);    // 비트 0 설정
    CLEAR_BIT(sfr->ctrl, 1);  // 비트 1 클리어
    return (sfr->ctrl == 0x1) ? 0 : 1;  // 비트 0만 설정된 상태 확인
}
