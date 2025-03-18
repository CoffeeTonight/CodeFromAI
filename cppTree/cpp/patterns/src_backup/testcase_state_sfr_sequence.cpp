// testcase_state_sfr_sequence.cpp
#include <stdint.h>

#define ASIC_BASE ((volatile uint32_t*)0xA0000000)

typedef struct {
    uint32_t ctrl;
    uint32_t data;
} AsicReg;

static AsicReg* asic = (AsicReg*)ASIC_BASE;

class AsicState {
public:
    virtual void handle(AsicReg* regs, uint32_t value) = 0;
};

class IdleState : public AsicState {
public:
    void handle(AsicReg* regs, uint32_t value) override {
        regs->data = value;
        regs->ctrl = 1;  // 시작
    }
};

class AsicDriver {
private:
    AsicState* state;
public:
    AsicDriver() : state(new IdleState()) {}
    void transfer(uint32_t value) { state->handle(asic, value); }
    ~AsicDriver() { delete state; }
};

int main() {
    AsicDriver driver;
    driver.transfer(0x5678);
    return (asic->data == 0x5678 && asic->ctrl == 1) ? 0 : 1;
}
