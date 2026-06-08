#include "icode.h"

ICODE_ENTRY(probe_sram_w_000)
{
    load_soc_addr(5, 0xA0000000u);
    bus_write32(5, 0x80000000u);
    vstop();
}
