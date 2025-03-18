// testcase_command_sfr_operation.cpp
#include <stdint.h>

#define SFR_BASE ((volatile uint32_t*)0xD0000000)

typedef struct {
    uint32_t cmd;
    uint32_t data;
} SfrReg;

static SfrReg* sfr = (SfrReg*)SFR_BASE;

class Command {
public:
    virtual void execute() = 0;
};

class WriteCommand : public Command {
private:
    uint32_t value;
public:
    WriteCommand(uint32_t v) : value(v) {}
    void execute() override {
        sfr->data = value;
        sfr->cmd = 1;
    }
};

class SfrDriver {
private:
    Command* command;
public:
    SfrDriver(Command* c) : command(c) {}
    void run() { command->execute(); }
    ~SfrDriver() { delete command; }
};

int main() {
    SfrDriver driver(new WriteCommand(0x5678));
    driver.run();
    return (sfr->data == 0x5678 && sfr->cmd == 1) ? 0 : 1;
}
