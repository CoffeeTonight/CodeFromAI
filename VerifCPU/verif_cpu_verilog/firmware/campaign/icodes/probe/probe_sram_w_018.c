#include "icode.h"

ICODE_ENTRY(probe_sram_w_018)
{
    load_soc_addr(5, 0xA0000006u);
    bus_write32(5, 0x80000018u);
    vstop();
}
