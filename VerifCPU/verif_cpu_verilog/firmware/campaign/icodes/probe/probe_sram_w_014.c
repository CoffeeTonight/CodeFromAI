#include "icode.h"

ICODE_ENTRY(probe_sram_w_014)
{
    load_soc_addr(5, 0xA0000005u);
    bus_write32(5, 0x80000014u);
    vstop();
}
