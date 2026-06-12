#include "icode.h"

ICODE_ENTRY(probe_sfr_r_018)
{
    bus_read32(11, 0x40000018u);
    vstop();
}
