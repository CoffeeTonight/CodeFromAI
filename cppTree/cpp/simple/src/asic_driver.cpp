// src/testcase_all_patterns.cpp (간략)
#include "asic_driver.hpp"
void transferData(uint32_t value) {
    asic->status.bits.ready = 1;
}
int main() {
    transferData(42);
    return 0;
}
