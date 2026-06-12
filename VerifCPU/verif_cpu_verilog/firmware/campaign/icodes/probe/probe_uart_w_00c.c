#include "icode.h"

ICODE_ENTRY(probe_uart_w_00c)
{
    load_soc_addr(5, 0xB0000003u);
    bus_write32(5, 0xC000000Cu);
    vstop();
}
