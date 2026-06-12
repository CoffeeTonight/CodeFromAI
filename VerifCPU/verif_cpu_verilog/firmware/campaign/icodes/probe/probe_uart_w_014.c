#include "icode.h"

ICODE_ENTRY(probe_uart_w_014)
{
    load_soc_addr(5, 0xB0000005u);
    bus_write32(5, 0xC0000014u);
    vstop();
}
