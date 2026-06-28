/* Alternate naming — harness must discover non-standard header */
#ifndef MMIO_MAP_H
#define MMIO_MAP_H

#define MMIO_APB_BASE 0x50000000u
#define MMIO_SRAM_BASE 0x60000000u

#define REG_SYS_CTRL  (MMIO_APB_BASE + 0x00u)
#define REG_SYS_CFG   (MMIO_APB_BASE + 0x04u)
#define REG_SYS_STAT  (MMIO_APB_BASE + 0x08u)

#define MEM_TEST0     (MMIO_SRAM_BASE + 0x00u)
#define MEM_TEST1     (MMIO_SRAM_BASE + 0x04u)

#endif