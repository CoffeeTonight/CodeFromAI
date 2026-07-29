# Auto-generated from campaign_slots.yaml — do not edit
# enabled=1: unique firmware; enabled=0: shares NOOP image at build time

CPU_SFR := name=SFR id=1 role=sfr pool_word=0x0000 enabled=1 phase_c=cpu_sfr/phase_c.c
CPU_SRAM := name=SRAM id=2 role=sram pool_word=0x0800 enabled=1 phase_c=cpu_sram/phase_c.c
CPU_UART := name=UART id=3 role=uart pool_word=0x1000 enabled=1 phase_c=cpu_uart/uart_fw.c

CPU_NAMES := SFR SRAM UART
CPU_ACTIVE := SFR SRAM UART