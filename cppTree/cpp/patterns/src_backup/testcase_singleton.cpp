// src/testcase_singleton.cpp
#include <stdint.h>

// SFR 레지스터 구조체 정의
typedef struct {
    uint32_t data;
} SfrReg;

// 싱글톤 클래스: SFR 접근 관리
class SfrManager {
private:
    static SfrManager* instance;  // 정적 인스턴스
    SfrReg* regs;                 // SFR 포인터

    // private 생성자
    SfrManager() : regs((SfrReg*)0xD0000000) {
        regs->data = 0;  // 초기화
    }

public:
    // 싱글톤 인스턴스 획득
    static SfrManager* getInstance() {
        if (!instance) {
            instance = new SfrManager();
        }
        return instance;
    }

    // SFR에 데이터 쓰기
    void setData(uint32_t value) {
        regs->data = value;
    }

    // SFR 데이터 읽기
    uint32_t getData() const {
        return regs->data;
    }

    // 소멸자 (테스트용, 실제로는 메모리 해제 주의 필요)
    ~SfrManager() {
        regs->data = 0xFFFF;  // 정리
    }
};

// 정적 멤버 초기화
SfrManager* SfrManager::instance = nullptr;

int main() {
    SfrManager* mgr = SfrManager::getInstance();
    mgr->setData(0xABCD);
    uint32_t result = mgr->getData();
    return (result == 0xABCD) ? 0 : 1;  // 싱글톤 동작 확인
}
