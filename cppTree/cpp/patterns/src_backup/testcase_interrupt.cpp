// src/testcase_interrupt.cpp
#include <stdint.h>

// 전역 SFR: 인터럽트 플래그
volatile uint32_t* interrupt_flag = (volatile uint32_t*)0xD0000010;

// 인터럽트 핸들러
void __attribute__((interrupt)) isr_handler() {
    *interrupt_flag = 0;  // 플래그 클리어
}

int main() {
    *interrupt_flag = 1;  // 인터럽트 트리거
    // 여기서는 ISR이 호출되었다고 가정하고 플래그 확인
    // 실제 하드웨어에서는 ISR이 자동 호출되지만, 테스트 목적으로 수동 확인
    isr_handler();  // 시뮬레이션용 직접 호출
    return (*interrupt_flag == 0) ? 0 : 1;  // ISR 후 플래그가 0인지 확인
}
