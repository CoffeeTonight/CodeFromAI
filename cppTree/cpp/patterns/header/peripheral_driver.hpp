#ifndef PERIPHERAL_DRIVER_HPP
#define PERIPHERAL_DRIVER_HPP

#include "sfr_registers.h"

enum OperationMode { MODE_IDLE, MODE_ACTIVE, MODE_TEST };

class PeripheralBase {
protected:
    PeripheralReg* regs;
    void configureRegisters();
    uint32_t getStatus();

public:
    PeripheralBase() : regs((PeripheralReg*)PERIPH_BASE) {}
    virtual void init() = 0;
};

class PeripheralDriver : public PeripheralBase {
private:
    uint32_t currentMode;

protected:
    void setMode(OperationMode mode);

public:
    PeripheralDriver() : currentMode(MODE_IDLE) {}
    void init() override;
    void processMode(uint32_t modeData);
    void processData(uint32_t inputData);
    uint32_t runTest(uint32_t testData, uint8_t iterations);
    uint32_t readOutput();
};

class AdvancedPeripheral : public PeripheralDriver {
public:
    void runTest(uint32_t testData, uint8_t iterations) {
        configureRegisters();
        regs->data_out.reg = testData * iterations;
    }
};

inline void PeripheralBase::configureRegisters() {
    regs->control.bits.enable = 1;
    regs->control.bits.data = 0;
    regs->data_in.reg = 0;
    regs->data_out.reg = 0;
}

inline uint32_t PeripheralBase::getStatus() {
    return regs->status.reg;
}

inline void PeripheralDriver::init() {
    configureRegisters();
    setMode(MODE_IDLE);
}

inline void PeripheralDriver::setMode(OperationMode mode) {
    currentMode = mode;
}

inline void PeripheralDriver::processMode(uint32_t modeData) {
    regs->control.bits.data = modeData & 0x1;
}

inline void PeripheralDriver::processData(uint32_t inputData) {
    regs->data_in.reg = inputData;
    regs->status.bits.status = (inputData > 0);
    regs->data_out.reg = inputData * 2;
}

inline uint32_t PeripheralDriver::runTest(uint32_t testData, uint8_t iterations) {
    configureRegisters();
    setMode(MODE_TEST);
    uint32_t result = 0;
    for (uint8_t i = 0; i < iterations; i++) {
        result += testData;
    }
    regs->data_out.reg = result;
    setMode(MODE_ACTIVE);
    return result;
}

inline uint32_t PeripheralDriver::readOutput() {
    return regs->data_out.reg;
}

#endif