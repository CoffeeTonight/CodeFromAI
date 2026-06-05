// CPU cluster (-f: paths relative to this file under filelists/)
+incdir+../include/common
+incdir+../include/hosts
+define+CPU_SUBSYS
../rtl/cpu/cpu_cluster.v
../rtl/leaves/cortex_a78_core.v
../rtl/leaves/riscv_host_core.v
../rtl/leaves/neoverse_core.v
