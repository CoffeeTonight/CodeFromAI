/* Reserved-slot / idle VCPU — immediate vstop (no bus traffic). */
#include "verif_insns.h"

void _start(void) {
    vstop();
    for (;;)
        ;
}