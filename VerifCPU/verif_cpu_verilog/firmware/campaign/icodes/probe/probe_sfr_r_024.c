#include "icode.h"

ICODE_ENTRY(probe_sfr_r_024)
{
    bus_read32(11, 0x40000024u);
    vstop();
}
