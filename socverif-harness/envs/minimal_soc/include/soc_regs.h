#ifndef SOC_REGS_H
#define SOC_REGS_H

#define SOC_SFR_BASE  0x40000000u
#define SOC_SRAM_BASE 0x80000000u

#define SFR_CTRL      (SOC_SFR_BASE + 0x00u)
#define SFR_CFG       (SOC_SFR_BASE + 0x04u)
#define SFR_STATUS    (SOC_SFR_BASE + 0x08u)

#define SRAM_MARKER   (SOC_SRAM_BASE + 0x00u)
#define SRAM_AUX      (SOC_SRAM_BASE + 0x04u)

#endif