#include "icode.h"

ICODE_ENTRY(probe_uart_r_018)
{
    bus_read32(11, 0xC0000018u);
    vstop();
}
