#include "icode.h"

ICODE_ENTRY(probe_sram_w_004)
{
    load_soc_addr(5, 0xA0000001u);
    bus_write32(5, 0x80000004u);
    vstop();
}
