// testcase_proxy_sfr_access.cpp
#include <stdint.h>

#define ASIC_BASE ((volatile uint32_t*)0xA0000000)

typedef struct {
    uint32_t data;
    uint32_t status;
} AsicReg;

static AsicReg* asic = (AsicReg*)ASIC_BASE;

class AsicProxy {
private:
    AsicReg* regs;
public:
    AsicProxy() : regs(asic) {}
    void writeData(uint32_t value) {
        if (regs->status & 0x1) {  // 상태 확인
            regs->data = value;
        }
    }
    uint32_t readData() {
        return (regs->status & 0x1) ? regs->data : 0;
    }
};

int main() {
    AsicProxy proxy;
    proxy.writeData(0x1234);
    uint32_t result = proxy.readData();
    return (result == 0x1234) ? 0 : 1;  // 테스트 통과 여부
}
