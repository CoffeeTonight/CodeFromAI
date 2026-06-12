#include "icode.h"

ICODE_ENTRY(probe_uart_r_014)
{
    bus_read32(11, 0xC0000014u);
    vstop();
}
