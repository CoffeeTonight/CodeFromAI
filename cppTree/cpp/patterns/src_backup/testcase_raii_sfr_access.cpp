// src/testcase_raii_sfr_access.cpp
#include <stdint.h>

// SFR 기본 주소 정의
#ifndef SFR_BASE_ADDR
#define SFR_BASE_ADDR 0xD0000000
#endif
#define SFR_BASE ((volatile uint32_t*)SFR_BASE_ADDR)

// SFR 레지스터 구조체 (그룹)
typedef struct {
    struct {
        uint32_t start : 1;  // 시작 비트
        uint32_t mode  : 2;  // 모드 (0: idle, 1: write)
    } bits;
    uint32_t reg;
} ControlReg;

typedef struct {
    uint32_t value;
} DataReg;

typedef struct {
    ControlReg ctrl;
    DataReg    data;
} SfrGroup;

// RAII 클래스: SFR 그룹 관리
class SfrGroupLock {
private:
    SfrGroup* group;
public:
    // 생성자: SFR 그룹 초기화
    SfrGroupLock() : group((SfrGroup*)SFR_BASE) {
        group->ctrl.bits.mode = 0;  // idle 모드
        group->ctrl.bits.start = 0; // 정지 상태
        group->data.value = 0x0;    // 데이터 초기화
    }

    // SFR 그룹에 데이터 쓰기
    void writeData(uint32_t value) {
        group->data.value = value;
        group->ctrl.bits.mode = 1;  // write 모드
        group->ctrl.bits.start = 1; // 시작
    }

    // SFR 그룹 데이터 읽기
    uint32_t readData() const {
        return group->data.value;
    }

    // 소멸자: SFR 그룹 정리
    ~SfrGroupLock() {
        group->ctrl.bits.start = 0; // 정지
        group->ctrl.bits.mode = 0;  // idle 모드
        group->data.value = 0xFFFF; // 데이터 클리어
    }
};

// 메인 함수: RAII 테스트
int main() {
    {
        SfrGroupLock lock;      // 객체 생성 -> SFR 그룹 초기화
        lock.writeData(0xDEAD); // SFR 그룹에 데이터 쓰기
        if (lock.readData() != 0xDEAD) return 1;  // 값 확인
        // 여기서 lock 소멸 -> SFR 그룹 정리
    }

    SfrGroup* group = (SfrGroup*)SFR_BASE;
    return (group->ctrl.bits.start == 0 && 
            group->ctrl.bits.mode == 0 && 
            group->data.value == 0xFFFF) ? 0 : 1;  // 소멸 후 상태 확인
}
