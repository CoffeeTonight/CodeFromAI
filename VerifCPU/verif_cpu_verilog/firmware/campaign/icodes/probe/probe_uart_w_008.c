#include "icode.h"

ICODE_ENTRY(probe_uart_w_008)
{
    load_soc_addr(5, 0xB0000002u);
    bus_write32(5, 0xC0000008u);
    vstop();
}
