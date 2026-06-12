#include "icode.h"

ICODE_ENTRY(probe_uart_r_01c)
{
    bus_read32(11, 0xC000001Cu);
    vstop();
}
