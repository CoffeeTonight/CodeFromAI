#include "icode.h"

ICODE_ENTRY(probe_uart_w_000)
{
    load_soc_addr(5, 0xB0000000u);
    bus_write32(5, 0xC0000000u);
    vstop();
}
