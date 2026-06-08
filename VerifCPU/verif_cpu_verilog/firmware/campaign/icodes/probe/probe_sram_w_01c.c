#include "icode.h"

ICODE_ENTRY(probe_sram_w_01c)
{
    load_soc_addr(5, 0xA0000007u);
    bus_write32(5, 0x8000001Cu);
    vstop();
}
