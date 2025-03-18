// asic_driver.hpp
#ifndef ASIC_DRIVER_HPP
#define ASIC_DRIVER_HPP

#include "asic_registers.h"

class AsicDriver {
public:
    AsicDriver() {}
    
    // SFR 그룹을 사용한 데이터 전송
    void transferData(uint32_t value) {
        while (!asic->status.bits.ready);  // 상태 확인
        asic->data.reg = value;            // 데이터 쓰기
        asic->ctrl.bits.mode = 1;          // 쓰기 모드
        asic->ctrl.bits.start = 1;         // 전송 시작
    }
    
    uint32_t readData() {
        while (!asic->status.bits.ready);  // 상태 확인
        asic->ctrl.bits.mode = 0;          // 읽기 모드
        asic->ctrl.bits.start = 1;         // 읽기 시작
        return asic->data.reg;             // 데이터 반환
    }
};

#endif
