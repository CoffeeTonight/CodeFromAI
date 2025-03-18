#include "sfr_registers.h"
#include "peripheral_driver.hpp"
#include "timer_registers.h"
#include "gpio_registers.h"

PeripheralReg* regs = (PeripheralReg*)PERIPH_BASE;

void configureTimer() {
    TimerRegs* timer = (TimerRegs*)TIMER_BASE;
    timer->bits.start = 1;
    timer->count = 1000;
}

#define a 0x100
void func() {
    *(int *)(a) = 1;
}

int main() {
    PeripheralDriver* peripheral = new PeripheralDriver();
    peripheral->init();
    peripheral->processMode(1);
    peripheral->processData(42);
    peripheral->runTest(100, 5);
    uint32_t result = peripheral->readOutput();

    configureTimer();

    gpio->bits.output = 1;
    gpio->value = 0xFF;
    func();
    return 0;
}