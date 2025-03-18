// testcase_observer_sfr_status.cpp
#include <stdint.h>

#define ASIC_BASE ((volatile uint32_t*)0xA0000000)

typedef struct {
    uint32_t status;
    uint32_t data;
} AsicReg;

static AsicReg* asic = (AsicReg*)ASIC_BASE;

class Observer {
public:
    virtual void update(uint32_t status) = 0;
};

class AsicMonitor : public Observer {
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
    void notify() { if (observer) observer->update(asic->status); }
};

int main() {
    AsicSubject subject;
    AsicMonitor monitor;
    subject.attach(&monitor);
    asic->status = 0xABCD;  // 상태 변경
    subject.notify();
    return (monitor.last_status == 0xABCD) ? 0 : 1;
}
