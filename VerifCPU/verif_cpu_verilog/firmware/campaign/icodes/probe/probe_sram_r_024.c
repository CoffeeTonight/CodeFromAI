#include "icode.h"

ICODE_ENTRY(probe_sram_r_024)
{
    bus_read32(11, 0x80000024u);
    vstop();
}
