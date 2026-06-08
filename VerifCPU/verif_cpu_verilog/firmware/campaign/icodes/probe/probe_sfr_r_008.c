#include "icode.h"

ICODE_ENTRY(probe_sfr_r_008)
{
    bus_read32(11, 0x40000008u);
    vstop();
}
