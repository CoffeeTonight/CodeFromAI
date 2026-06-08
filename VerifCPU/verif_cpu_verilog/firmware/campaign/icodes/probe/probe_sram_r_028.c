#include "icode.h"

ICODE_ENTRY(probe_sram_r_028)
{
    bus_read32(11, 0x80000028u);
    vstop();
}
