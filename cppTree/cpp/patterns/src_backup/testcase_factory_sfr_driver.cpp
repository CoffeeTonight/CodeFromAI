// testcase_factory_sfr_driver.cpp
#include <stdint.h>
#include <cstring>

#define PCIE_BASE ((volatile uint32_t*)0xB0000000)

typedef struct {
    uint32_t config;
} PcieReg;

static PcieReg* pcie = (PcieReg*)PCIE_BASE;

class Driver {
public:
    virtual void configure() = 0;
};

class PcieDriver : public Driver {
public:
    void configure() override { pcie->config = 0x1; }
};

class DriverFactory {
public:
    static Driver* create(const char* type) {
        if (strcmp(type, "pcie") == 0) return new PcieDriver();
        return nullptr;
    }
};

int main() {
    Driver* driver = DriverFactory::create("pcie");
    if (driver) {
        driver->configure();
        delete driver;
    }
    return (pcie->config == 0x1) ? 0 : 1;
}
