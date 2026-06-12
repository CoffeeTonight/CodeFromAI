#include "icode.h"

ICODE_ENTRY(probe_uart_r_008)
{
    bus_read32(11, 0xC0000008u);
    vstop();
}
