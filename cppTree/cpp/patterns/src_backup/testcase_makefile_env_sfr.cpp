// testcase_makefile_env_sfr.cpp
#include <stdint.h>

#ifndef SFR_BASE_ADDR  // Makefile에서 -D로 정의 가능
#define SFR_BASE_ADDR 0xD0000000
#endif

#define SFR_BASE ((volatile uint32_t*)SFR_BASE_ADDR)

typedef struct {
    uint32_t config;
} SfrReg;

static SfrReg* sfr = (SfrReg*)SFR_BASE;

int main() {
    sfr->config = 0xBEEF;  // 환경 변수로 설정된 주소에 쓰기
    return (sfr->config == 0xBEEF) ? 0 : 1;
}
