// src/testcase_all_patterns.cpp
#include "sfr_base.h"
#include "sfr_control.h"
#include "sfr_status.h"
#include <cstring>
#include <stdint.h>

/*
 * 설계 패턴 번호 매핑:
 * 1: ANSI-C 매크로 (Macro)
 * 2: ANSI-C 함수 포인터 (Function Pointer)
 * 3: ANSI-C 직접 포인터 조작 (Direct Pointer Access)
 * 4: ANSI-C 직접 메모리 접근 (Raw Memory Access)
 * 5: ANSI-C 별칭 (Alias)
 * 6: RAII (Resource Acquisition Is Initialization)
 * 7: Singleton
 * 8: Proxy
 * 9: State
 * 10: Factory
 * 11: Observer
 * 12: Command
 * 13: Template
 * 14: ISR (Interrupt Service Routine)
 * 15: FSM (Finite State Machine)
 * 추가: 조건문 패턴 (#ifdef, #ifndef, #elif, #else)
 */

#define FEATURE_A 1
#define FEATURE_B 0
#define DEBUG_MODE 1

// ANSI-C 스타일 매크로 (1)
#define SET_BIT1(reg, bit) ((reg) |= (1U << (bit)))
#define CLEAR_BIT1(reg, bit) ((reg) &= ~(1U << (bit)))
#define REG_OFFSET3(base, offset) ((volatile uint32_t*)((base) + (offset)))

// SFR 구조체 통합
typedef struct {
    ControlReg ctrl1;
    DataReg    data3;
    StatusReg  status4;
} AsicReg;

static AsicReg* asic = (AsicReg*)ASIC_BASE;

// ANSI-C 스타일 별칭 (5)
#define CTRL_ALIAS5 asic->ctrl1.reg

// ANSI-C 스타일: 특정 주소 직접 접근 (4)
#define SFR_TEST_ADDR4 0x100
void ansi_c_raw_access4() {
    *(volatile uint32_t *)(SFR_TEST_ADDR4) = 0x1;
}

// ANSI-C 스타일: 함수 포인터 (2)
enum OperationMode2 {
    MODE_IDLE2  = 0,
    MODE_WRITE2 = 1,
    MODE_READ2  = 2
};

typedef struct {
    void (*handle2)(AsicReg* regs);
    enum OperationMode2 mode;
} AsicOperation2;

void write_handler2(AsicReg* regs) {
    SET_BIT1(regs->ctrl1.reg, 1);
    regs->ctrl1.reg |= (MODE_WRITE2 << 2);
}

static AsicOperation2 operations2[] = {
    { write_handler2, MODE_WRITE2 }
};

// ANSI-C 스타일: 직접 포인터 조작 (3)
void ansi_c_direct_access3(volatile uint32_t* base) {
    volatile uint32_t* ctrl_reg = REG_OFFSET3(base, 0);
    *ctrl_reg = 0xBEEF;
}

// RAII Pattern (6)
class SfrLock6 {
public:
    SfrLock6() { asic->ctrl1.bits.start = 0; }
    ~SfrLock6() { asic->status4.bits.ready = 0; }
};

// Singleton Pattern (7)
class SfrManager7 {
private:
    static SfrManager7* instance;
    SfrManager7() { asic->data3.data = 0xDEAD; }
public:
    static SfrManager7* getInstance() {
        if (!instance) instance = new SfrManager7();
        return instance;
    }
    void reset7() { asic->ctrl1.reg = 0; }
};
SfrManager7* SfrManager7::instance = nullptr;

// Proxy Pattern (8)
class AsicProxy8 {
private:
    AsicReg* regs;
public:
    AsicProxy8() : regs(asic) {}
    void safeWrite8(uint32_t value) {
        if (regs->status4.bits.ready) regs->data3.data = value;
    }
};

// State Pattern (9)
class AsicState9 {
public:
    virtual void handle9(AsicReg* regs) = 0;
};

class WriteState9 : public AsicState9 {
public:
    void handle9(AsicReg* regs) override {
        regs->ctrl1.bits.mode = MODE_WRITE2;
        regs->ctrl1.bits.start = 1;
    }
};

// Factory Pattern (10)
class Driver10 {
public:
    virtual void configure10() = 0;
};

class ControlDriver10 : public Driver10 {
public:
    void configure10() override { asic->ctrl1.bits.start = 1; }
};

class DriverFactory10 {
public:
    static Driver10* create10(const char* type) {
        if (strcmp(type, "control") == 0) return new ControlDriver10();
        return nullptr;
    }
};

// Observer Pattern (11)
class Observer11 {
public:
    virtual void update11(uint32_t status) = 0;
};

class StatusMonitor11 : public Observer11 {
public:
    uint32_t last_status = 0;
    void update11(uint32_t status) override { last_status = status; }
};

class AsicSubject11 {
private:
    Observer11* observer;
public:
    AsicSubject11() : observer(nullptr) {}
    void attach11(Observer11* obs) { observer = obs; }
    void notify11() { if (observer) observer->update11(asic->status4.reg); }
};

// Command Pattern (12)
class Command12 {
public:
    virtual void execute12() = 0;
};

class ReadCommand12 : public Command12 {
public:
    void execute12() override {
        asic->ctrl1.bits.mode = MODE_READ2;
        asic->ctrl1.bits.start = 1;
    }
};

// Template Pattern (13)
class AsicWorkflow13 {
protected:
    virtual void process13() = 0;
public:
    void execute13() {
        asic->status4.reg = 0;
        process13();
        asic->status4.bits.ready = 1;
    }
};

class DataProcess13 : public AsicWorkflow13 {
protected:
    void process13() override { asic->data3.data = ~asic->data3.data; }
};

// ISR Pattern (14)
void ISR_Handler14() {
    asic->status4.reg &= ~0x1;
}

// FSM Pattern (15)
enum FsmState15 { INIT15, RUNNING15, STOPPED15 };
void run_fsm15(AsicReg* regs) {
    static enum FsmState15 state = INIT15;
    switch (state) {
        case INIT15: regs->ctrl1.reg = 0x1; state = RUNNING15; break;
        case RUNNING15: regs->data3.data = 0x2; state = STOPPED15; break;
        case STOPPED15: regs->status4.reg = 0x3; break;
    }
}

// Main 함수
int main() {
    // ANSI-C 스타일 호출
    ansi_c_raw_access4();
    ansi_c_direct_access3(ASIC_BASE);
    operations2[0].handle2(asic);

    // RAII
    SfrLock6 lock;

    // Singleton
    SfrManager7* mgr = SfrManager7::getInstance();
    mgr->reset7();

    // Proxy
    AsicProxy8 proxy;
    proxy.safeWrite8(0x1234);

    // State
    WriteState9 state;
    state.handle9(asic);

    // Factory
    Driver10* driver = DriverFactory10::create10("control");
    if (driver) {
        driver->configure10();
        delete driver;
    }

    // Observer
    AsicSubject11 subject;
    StatusMonitor11 monitor;
    subject.attach11(&monitor);
    asic->status4.reg = 0xFFFF;
    subject.notify11();

    // Command
    Command12* cmd = new ReadCommand12();
    cmd->execute12();
    delete cmd;

    // Template
    DataProcess13 workflow;
    workflow.execute13();

    // ISR
    ISR_Handler14();

    // FSM
    run_fsm15(asic);

    // 복잡한 조건문 (#ifdef, #elif, #ifndef 포함)
    #ifdef FEATURE_A
        if (DEBUG_MODE == 1) {
            CTRL_ALIAS5 = 0x1111;
            asic->data3.data = 0xAAAA;
        } else {
            asic->status4.reg = 0x2222;
        }
    #elif FEATURE_B
        asic->ctrl1.reg = 0x3333;
    #else
        asic->data3.data = 0x4444;
    #endif

    #ifndef FEATURE_C  // FEATURE_C가 정의되지 않았을 때 실행
        asic->ctrl1.reg = 0x5555;
    #else
        asic->status4.reg = 0x6666;
    #endif

    // 테스트 결과 검증
    bool pass = (asic->data3.data == ~0x1234 && 
                 asic->ctrl1.bits.start == 1 && 
                 monitor.last_status == 0xFFFF && 
                 CTRL_ALIAS5 == 0x1111);
    return pass ? 0 : 1;
}
