#include "icode.h"

ICODE_ENTRY(probe_sram_w_008)
{
    load_soc_addr(5, 0xA0000002u);
    bus_write32(5, 0x80000008u);
    vstop();
}
