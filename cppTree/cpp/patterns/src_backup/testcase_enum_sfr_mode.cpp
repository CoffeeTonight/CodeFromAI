// testcase_enum_sfr_mode.cpp
#include <stdint.h>

#define ASIC_BASE ((volatile uint32_t*)0xA0000000)

typedef struct {
    uint32_t mode;
} AsicReg;

static AsicReg* asic = (AsicReg*)ASIC_BASE;

enum class TransferMode : uint32_t {
    READ = 0,
    WRITE = 1,
    IDLE = 2
};

class AsicDriver {
public:
    void setMode(TransferMode mode) {
        asic->mode = static_cast<uint32_t>(mode);
    }
};

int main() {
    AsicDriver driver;
    driver.setMode(TransferMode::WRITE);
    return (asic->mode == 1) ? 0 : 1;
}
