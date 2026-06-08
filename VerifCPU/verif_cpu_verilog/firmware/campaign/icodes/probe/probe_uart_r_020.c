#include "icode.h"

ICODE_ENTRY(probe_uart_r_020)
{
    bus_read32(11, 0xC0000020u);
    vstop();
}
