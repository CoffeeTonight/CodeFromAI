#include "icode.h"
#include "soc_regs.h"

ICODE_ENTRY(check_uart_irq)
{
    bus_read32(11, UART_IRQ_HANG);
    vstop();
}