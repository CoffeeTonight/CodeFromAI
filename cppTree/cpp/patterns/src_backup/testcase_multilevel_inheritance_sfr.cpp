// testcase_multilevel_inheritance_sfr.cpp
#include <stdint.h>

#define SFR_BASE ((volatile uint32_t*)0xD0000000)

typedef struct {
    uint32_t ctrl;
    uint32_t data;
} SfrReg;

static SfrReg* sfr = (SfrReg*)SFR_BASE;

class BaseDriver {
protected:
    void resetSfr() { sfr->ctrl = 0; }
};

class MidConfigDriver : public BaseDriver {
protected:
    void configSfr(uint32_t value) { sfr->data = value; }
};

class MidControlDriver : public MidConfigDriver {
protected:
    void startSfr() { sfr->ctrl = 1; }
};

class FinalDriver : public MidControlDriver {
public:
    void execute() {
        resetSfr();      // 1단계: Base
        configSfr(0x1234);  // 2단계: MidConfig
        startSfr();      // 3단계: MidControl
    }
};

int main() {
    FinalDriver driver;
    driver.execute();
    return (sfr->data == 0x1234 && sfr->ctrl == 1) ? 0 : 1;
}
