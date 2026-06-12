#include "icode.h"

ICODE_ENTRY(probe_uart_r_004)
{
    bus_read32(11, 0xC0000004u);
    vstop();
}
