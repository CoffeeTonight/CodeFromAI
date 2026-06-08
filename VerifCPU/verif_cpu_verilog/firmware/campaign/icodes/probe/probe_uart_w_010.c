#include "icode.h"

ICODE_ENTRY(probe_uart_w_010)
{
    load_soc_addr(5, 0xB0000004u);
    bus_write32(5, 0xC0000010u);
    vstop();
}
