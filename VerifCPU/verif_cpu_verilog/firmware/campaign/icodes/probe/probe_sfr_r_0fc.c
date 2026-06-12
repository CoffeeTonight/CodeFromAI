#include "icode.h"

ICODE_ENTRY(probe_sfr_r_0fc)
{
    bus_read32(11, 0x400000FCu);
    vstop();
}
