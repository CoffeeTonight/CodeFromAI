// testcase_ifdef_sfr_config.cpp
#include <stdint.h>

#define SFR_BASE ((volatile uint32_t*)0xD0000000)

typedef struct {
    uint32_t mode;
} SfrReg;

static SfrReg* sfr = (SfrReg*)SFR_BASE;

#define DEBUG_MODE 1
#define PERFORMANCE_MODE 0

int main() {
    #ifdef DEBUG_MODE
        #if DEBUG_MODE == 1
            sfr->mode = 0xDEAD;  // 디버그 모드 설정
        #elif PERFORMANCE_MODE == 1
            sfr->mode = 0xBEEF;  // 성능 모드 설정
        #else
            sfr->mode = 0xCAFE;  // 기본 모드
        #endif
    #else
        sfr->mode = 0xFACE;  // 디버그 비활성
    #endif
    return (sfr->mode == 0xDEAD) ? 0 : 1;
}
