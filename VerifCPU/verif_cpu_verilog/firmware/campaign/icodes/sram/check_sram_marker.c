#include "icode.h"
#include "soc_regs.h"

ICODE_ENTRY(check_sram_marker)
{
    bus_read32(11, SRAM_MARKER);
    vstop();
}