#include "icode.h"

ICODE_ENTRY(probe_sfr_r_020)
{
    bus_read32(11, 0x40000020u);
    vstop();
}
