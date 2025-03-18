// src/testcase_all_patterns.cpp
#include "sfr_base.h"
#include "sfr_control.h"
#include "sfr_status.h"
#include <cstring>  // strcmp을 위해 추가

#define FEATURE_A 1
#define FEATURE_B 0

// SFR 구조체 통합
typedef struct {
    ControlReg ctrl;
    DataReg    data;
    StatusReg  status;
} AsicReg;

static AsicReg* asic = (AsicReg*)ASIC_BASE;

// Enum 선언
enum class OperationMode : uint32_t {
    IDLE  = 0,
    WRITE = 1,
    READ  = 2
};

// Proxy Pattern
class AsicProxy {
private:
    AsicReg* regs;
public:
    AsicProxy() : regs(asic) {}
    void safeWrite(uint32_t value) {
        if (regs->status.bits.ready) regs->data.data = value;
    }
};

// State Pattern
class AsicState {
public:
    virtual void handle(AsicReg* regs) = 0;
};

class WriteState : public AsicState {
public:
    void handle(AsicReg* regs) override {
        regs->ctrl.bits.mode = static_cast<uint32_t>(OperationMode::WRITE);
        regs->ctrl.bits.start = 1;
    }
};

// Factory Pattern
class Driver {
public:
    virtual void configure() = 0;
};

class ControlDriver : public Driver {
public:
    void configure() override { asic->ctrl.bits.start = 1; }
};

class DriverFactory {
public:
    static Driver* create(const char* type) {
        if (strcmp(type, "control") == 0) return new ControlDriver();
        return nullptr;
    }
};

// Observer Pattern
class Observer {
public:
    virtual void update(uint32_t status) = 0;
};

class StatusMonitor : public Observer {
public:
    uint32_t last_status = 0;
    void update(uint32_t status) override { last_status = status; }
};

class AsicSubject {
private:
    Observer* observer;
public:
    AsicSubject() : observer(nullptr) {}
    void attach(Observer* obs) { observer = obs; }
    void notify() { if (observer) observer->update(asic->status.reg); }
};

// Multilevel Inheritance
class BaseDriver {
protected:
    void initSfr() { asic->ctrl.reg = 0; }
};

class MidDriver : public BaseDriver {
protected:
    void setData(uint32_t value) { asic->data.data = value; }
};

class FinalDriver : public MidDriver {
public:
    void run() {
        initSfr();
        setData(0xABCD);
        asic->ctrl.bits.start = 1;
    }
};

// Command Pattern
class Command {
public:
    virtual void execute() = 0;
};

class ReadCommand : public Command {
public:
    void execute() override {
        asic->ctrl.bits.mode = static_cast<uint32_t>(OperationMode::READ);
        asic->ctrl.bits.start = 1;
    }
};

// Template Pattern
class AsicWorkflow {
protected:
    virtual void process() = 0;
public:
    void execute() {
        asic->status.reg = 0;  // 준비
        process();
        asic->status.bits.ready = 1;  // 완료
    }
};

class DataProcess : public AsicWorkflow {
protected:
    void process() override { asic->data.data = ~asic->data.data; }
};

// Main 함수 (모든 패턴 통합)
int main() {
    // Proxy
    AsicProxy proxy;
    proxy.safeWrite(0x1234);

    // State
    WriteState state;
    state.handle(asic);

    // Factory
    Driver* driver = DriverFactory::create("control");
    if (driver) {
        driver->configure();
        delete driver;
    }

    // Observer
    AsicSubject subject;
    StatusMonitor monitor;
    subject.attach(&monitor);
    asic->status.reg = 0xFFFF;
    subject.notify();

    // Multilevel Inheritance
    FinalDriver final;
    final.run();

    // Command
    Command* cmd = new ReadCommand();
    cmd->execute();
    delete cmd;

    // Template
    DataProcess workflow;
    workflow.execute();

    // #ifdef 중첩
    #ifdef FEATURE_A
        #if FEATURE_A == 1
            asic->ctrl.reg = 0x1111;
        #elif FEATURE_B == 1
            asic->data.data = 0x2222;
        #else
            asic->status.reg = 0x3333;
        #endif
    #else
        asic->ctrl.reg = 0x4444;
    #endif

    // 테스트 결과 검증
    bool pass = (asic->data.data == ~0x1234 && 
                 asic->ctrl.bits.start == 1 && 
                 monitor.last_status == 0xFFFF && 
                 asic->ctrl.reg == 0x1111);
    return pass ? 0 : 1;
}
