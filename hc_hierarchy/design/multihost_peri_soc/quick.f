// Fast index subset (structural hierarchy smoke)
+incdir+./include/common
+incdir+./include/peri
+define+ORION_SOC
+define+QUICK_BUILD
-f filelists/cpu_subsys.f
-f filelists/peri_cluster.f
rtl/top/orion_soc_top.v
rtl/gpu/gpu_slice.v
rtl/mem/memory_subsystem.v
-F filelists/io_hosts.f
-f filelists/parse_stress.f
+incdir+./include/param
