#include <stdint.h>

#define SFR_BASE_ADDR 0xD0000000
#define SFR_BASE SFR_BASE_ADDR

typedef struct {
    uint32_t ctrl;
    uint32_t status;
} SfrReg;

volatile SfrReg* sfr = (SfrReg*)SFR_BASE;

void configure_status_bit(int bit) {
    sfr->status |= (1 << bit);
}

void update_control(int ctrl_bit, int status_bit) {
    sfr->status &= ~(1 << ctrl_bit);
    configure_status_bit(3); // 상수 값 사용
}

void process_step(int step, int ctrl_bit, int status_bit) {
    if (step > 0 && step < 5) {
        sfr->status |= (1 << ctrl_bit);
    }
    update_control(ctrl_bit, status_bit);
}

void handle_operation(int a, int b, int c) {
    if (sfr->status == 0) {
        process_step(a, b, c);
    }
}

void execute_task(int task) {
    handle_operation(task, task + 1, task + 2);
}

int main() {
    for (int i = 0; i < 5; i++) {
        sfr->ctrl = 0;
        execute_task(i);
    }
    execute_task(5);
    process_step(1, 2, 3); // 상수 값 전달
    return sfr->status == 0;
}
