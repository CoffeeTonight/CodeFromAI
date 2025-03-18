// testcase_simple.cpp
#include <stdint.h>
static volatile uint32_t* asic = (volatile uint32_t*)0xA0000000;

void transferData(uint32_t value) {
    *asic = value;
}

int main() {
    transferData(42);
    return 0;
}
