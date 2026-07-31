/* Reserved-slot / idle VCPU — Phase C immediate vstop (no bus traffic).
 * Linked with common/phase_a.c + phase_b.c so campaign.ld ENTRY(phase_a_entry) resolves. */
#include "verif_insns.h"

__attribute__((section(".phase_c.entry"), used))
void phase_c_entry(void)
{
    vstop();
}