#include "icode.h"

ICODE_ENTRY(probe_uart_w_01c)
{
    load_soc_addr(5, 0xB0000007u);
    bus_write32(5, 0xC000001Cu);
    vstop();
}
