#include "icode.h"

ICODE_ENTRY(probe_sram_w_00c)
{
    load_soc_addr(5, 0xA0000003u);
    bus_write32(5, 0x8000000Cu);
    vstop();
}
