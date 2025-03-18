// src/testcase_template_sfr_workflow.cpp
#include <stdint.h>

#define SFR_BASE ((volatile uint32_t*)0xD0000000)

typedef struct {
    uint32_t ctrl;
    uint32_t data;
} SfrReg;

static SfrReg* sfr = (SfrReg*)SFR_BASE;

class SfrWorkflow {
protected:
    virtual void process() = 0;
public:
    void execute() {
        sfr->ctrl = 0;  // 초기화
        process();
        sfr->ctrl = 1;  // 완료
    }
};

class DataInvert : public SfrWorkflow {
protected:
    void process() override { sfr->data = ~sfr->data; }
};

int main() {
    sfr->data = 0xFFFF;
    DataInvert workflow;
    workflow.execute();
    return (sfr->data == (uint32_t)~0xFFFF && sfr->ctrl == 1) ? 0 : 1;  // 명시적 캐스팅으로 경고 제거
}
