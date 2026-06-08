// =============================================================================
// Orion multihost SoC — VCS / Xcelium (xrun) filelist reference
// Parsed by hc_hierarchy ingest (directives without RTL are skipped safely)
// =============================================================================

# Run from design/multihost_peri_soc with:
#   export ORION_RTL_ROOT=$(pwd)

+incdir+${ORION_RTL_ROOT}/include/common
+incdir+${ORION_RTL_ROOT}/include/hosts
+incdir+${ORION_RTL_ROOT}/include/peri
+incdir+./include/common
+incdir+./include/hosts+./include/peri

+define+ORION_SOC
+define+NUM_CPU=4
+define+NUM_GPU=2
+define+ENABLE_I3C
+define+ENABLE_SPI_SLAVE
+define+SIM_SPEEDUP
+define+UART_BAUD=115200

+libext+.v+.sv+.vh+.svh
-y ${ORION_RTL_ROOT}/libs/vendor
-y ./libs/vendor
-v ./libs/blackbox_pcie.v
-v ${ORION_RTL_ROOT}/libs/blackbox_pcie.v

// Simulator-only (ignored by hc ingest, documented for EDA)
-timescale 1ns/1ps
+nospecify
+notimingchecks
-top orion_soc_top

// Nested lists: -f (relative to this .f dir), -F (relative to cwd)
-f filelists/cpu_subsys.f
-f filelists/gpu_subsys.f
-f filelists/mem_subsys.f
-F filelists/io_hosts.f
-f filelists/nested/deep_wrap.f
-f filelists/parse_stress.f

+incdir+${ORION_RTL_ROOT}/include/param
+incdir+./include/param

// Top + fabric (multiple RTL on one line)
rtl/top/orion_soc_top.v rtl/leaves/noc_mesh.v

// Explicit env-based path
${ORION_RTL_ROOT}/rtl/leaves/axi_crossbar.v
