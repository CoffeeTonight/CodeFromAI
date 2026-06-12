#include "icode.h"

ICODE_ENTRY(probe_sfr_r_010)
{
    bus_read32(11, 0x40000010u);
    vstop();
}
