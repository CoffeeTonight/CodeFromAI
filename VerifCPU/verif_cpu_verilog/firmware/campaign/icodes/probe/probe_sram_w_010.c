#include "icode.h"

ICODE_ENTRY(probe_sram_w_010)
{
    load_soc_addr(5, 0xA0000004u);
    bus_write32(5, 0x80000010u);
    vstop();
}
