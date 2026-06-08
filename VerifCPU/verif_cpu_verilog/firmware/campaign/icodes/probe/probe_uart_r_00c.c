#include "icode.h"

ICODE_ENTRY(probe_uart_r_00c)
{
    bus_read32(11, 0xC000000Cu);
    vstop();
}
