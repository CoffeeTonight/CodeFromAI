// src/testcase_memorymapped.cpp
#include <stdint.h>

// 동일한 SFR에 대한 별칭 정의
#define REG_ALIAS1 ((volatile uint32_t*)0xD0000000)
#define REG_ALIAS2 ((volatile uint32_t*)0xD0000000)

int main() {
    *REG_ALIAS1 = 0xABCD;  // 첫 번째 별칭으로 쓰기
    return (*REG_ALIAS2 == 0xABCD) ? 0 : 1;  // 두 번째 별칭으로 읽기 확인
}
