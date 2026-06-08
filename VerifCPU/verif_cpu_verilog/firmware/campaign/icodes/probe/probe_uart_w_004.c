#include "icode.h"

ICODE_ENTRY(probe_uart_w_004)
{
    load_soc_addr(5, 0xB0000001u);
    bus_write32(5, 0xC0000004u);
    vstop();
}
