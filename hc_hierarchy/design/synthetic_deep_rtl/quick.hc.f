// Fast CI shallow subset (~25 sources). Full deep: quick_deep.hc.f
+incdir+./common_inc
+incdir+./inc_level0
+define+SOC_TOP
-top deep_soc_top
rtl/deep_soc_top.v
rtl/u_jupiter_noc.v
rtl/u_pmu.v
rtl/u_system_control.v
rtl/soc_top/u_ecc_engine_00/ecc_engine.v
rtl/soc_top/u_ecc_engine_00/u_jpeg_encoder_00/jpeg_encoder.v
rtl/soc_top/u_ecc_engine_00/u_jpeg_encoder_00/u_dsp_vector_01/dsp_vector.v
rtl/soc_top/u_ecc_engine_00/u_jpeg_encoder_00/u_dsp_vector_01/u_video_codec_00/video_codec.v
rtl/soc_top/u_ecc_engine_00/u_jpeg_encoder_00/u_isp_pipeline_00/isp_pipeline.v
rtl/soc_top/u_ecc_engine_00/u_thermal_sensor_01/thermal_sensor.v
rtl/soc_top/u_ecc_engine_00/u_thermal_sensor_01/u_pll_00/pll.v
rtl/soc_top/u_ecc_engine_00/u_thermal_sensor_01/u_pmu_02/pmu.v
rtl/soc_top/u_ecc_engine_00/u_thermal_sensor_01/u_secure_boot_rom_01/secure_boot_rom.v
rtl/soc_top/u_ecc_engine_00/u_thermal_sensor_01/u_secure_boot_rom_01/u_vpu_00/vpu.v
rtl/soc_top/u_ecc_engine_00/u_thermal_sensor_01/u_pll_00/u_ecc_engine_02/ecc_engine.v
rtl/soc_top/u_ecc_engine_00/u_thermal_sensor_01/u_pll_00/u_pwm_controller_01/pwm_controller.v
rtl/soc_top/u_ecc_engine_00/u_thermal_sensor_01/u_pll_00/u_rtc_00/rtc.v
rtl/soc_top/u_ecc_engine_00/u_thermal_sensor_01/u_pmu_02/u_neoverse_n1_01/neoverse_n1.v
rtl/soc_top/u_ecc_engine_00/u_thermal_sensor_01/u_pmu_02/u_pcie_gen4_00/pcie_gen4.v
rtl/soc_top/u_ecc_engine_00/u_vpu_02/vpu.v
rtl/soc_top/u_gpu_shader_cluster_01/gpu_shader_cluster.v
rtl/soc_top/u_key_manager_03/key_manager.v
rtl/soc_top/u_nvme_host_02/nvme_host.v