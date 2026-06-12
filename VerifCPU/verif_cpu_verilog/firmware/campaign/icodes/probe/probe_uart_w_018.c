#include "icode.h"

ICODE_ENTRY(probe_uart_w_018)
{
    load_soc_addr(5, 0xB0000006u);
    bus_write32(5, 0xC0000018u);
    vstop();
}
