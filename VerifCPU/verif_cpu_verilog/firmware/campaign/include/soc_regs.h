#ifndef SOC_REGS_H
#define SOC_REGS_H

#include <stdint.h>

#define SOC_SFR_BASE  0x40000000u
#define SOC_SRAM_BASE 0x80000000u
#define SOC_UART_BASE 0xC0000000u

#define SFR_CTRL      (SOC_SFR_BASE + 0x00u)
#define SFR_CFG       (SOC_SFR_BASE + 0x04u)
#define SFR_CLK       (SOC_SFR_BASE + 0x08u)
#define SFR_INT_EN    (SOC_SFR_BASE + 0x0Cu)
#define SFR_DMA_SRC   (SOC_SFR_BASE + 0x10u)
#define SFR_DMA_DST   (SOC_SFR_BASE + 0x14u)
#define SFR_STATUS    (SOC_SFR_BASE + 0x18u)
#define SFR_GPIO_DIR  (SOC_SFR_BASE + 0x1Cu)
#define SFR_GPIO_OUT  (SOC_SFR_BASE + 0x20u)
#define SFR_GPIO_IN   (SOC_SFR_BASE + 0x24u)
#define SFR_WDT       (SOC_SFR_BASE + 0x28u)
#define SFR_VERSION   (SOC_SFR_BASE + 0x2Cu)
#define SFR_XZ_PORT   (SOC_SFR_BASE + 0xFCu)

#define SRAM_MARKER   (SOC_SRAM_BASE + 0x00u)
#define SRAM_AUX      (SOC_SRAM_BASE + 0x04u)

#define UART_BAUD     (SOC_UART_BASE + 0x00u)
#define UART_IRQ_HANG (SOC_UART_BASE + 0x10u)

#endif