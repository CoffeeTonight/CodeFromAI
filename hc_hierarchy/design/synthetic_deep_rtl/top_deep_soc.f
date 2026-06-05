// Deep SoC test filelist (max depth 10, ~1000 instances)
// Generated: 2026-06-01T14:21:41.936302

+incdir+./common_inc
+incdir+./inc_level0
+define+SOC_TOP
+define+DEBUG=1

// Environment variable test
+incdir+./common_inc

-v ./single_lib.v

-y ./libs/tech_lib
+libext+.v

// === Recursive +incdir chain example ===
// top declares inc_level0 + common_inc
//   -> subsys_XX.f additionally declares inc_levelX
//      -> deep .v files can `include headers from any accumulated level
-f u_ecc_engine_00.f
-f u_gpu_shader_cluster_01.f
-f u_key_manager_03.f
-f u_nvme_host_02.f

// Additional syntax / nested tests
rtl/u_jupiter_noc.v
rtl/u_system_control.v
rtl/u_pmu.v

# Hash comment test
// End of top filelist

// Include deeply nested filelist
-f nested_deep/deep_includes.f
