# =============================================================================
# VerifCPU List - CPU Definition File
# =============================================================================
# Format:
#   CPU_XXX := name=STRING id=NUMBER role=ROLE src_dir=DIR start_offset=HEX
#
# - name     : Human-readable name (used in console/harness, e.g. DMA, SFR, SRAM)
# - id       : Numeric ID (used internally, for RTL, arrays, etc.)
# - role     : Build role (determines which main logic to use)
# - src_dir  : Directory containing the role-specific sources
# - start_offset : Starting address in the unified memory map
#
# You can freely add/remove CPUs here. Up to 55+ is fine.
# =============================================================================

# Example CPUs with meaningful names
CPU_DMA     := name=DMA     id=0  role=master     src_dir=cpu_master      start_offset=0x00000000
CPU_SFR     := name=SFR     id=1  role=observer   src_dir=cpu_observer    start_offset=0x00010000
CPU_SRAM    := name=SRAM    id=2  role=worker     src_dir=cpu_worker      start_offset=0x00020000
CPU_IRQ     := name=IRQ     id=3  role=trouble    src_dir=cpu_trouble     start_offset=0x00030000
CPU_AHB_M0  := name=AHB_M0  id=4  role=master     src_dir=cpu_master      start_offset=0x00040000

# You can add more like this:
# CPU_05      := name=UART    id=5  role=worker     src_dir=cpu_worker      start_offset=0x00050000
# CPU_06      := name=GPIO    id=6  role=observer   src_dir=cpu_observer    start_offset=0x00060000

# =============================================================================
# Notes:
# - 'name' is what you will mostly use in console and harness (cpu DMA stall)
# - 'id' is the numeric identifier that can be passed to RTL or used in arrays
# - 'role' decides which firmware logic (main.c style) to compile
# - 'start_offset' is used when merging all .bin into one unified memory image
# =============================================================================