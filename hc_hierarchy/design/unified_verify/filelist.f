// Unified verification corpus — fast index, Windows-safe short paths
+incdir+./include
+incdir+./rtl/hfa
+define+HC_VERIFY
+define+USE_ALT=1
+define+ENABLE=1
+define+USE_M1
-y lib
-f fl/cells.f
-f fl/ghost.f
-f fl/midsub_module.f
-f fl/test_file.f
rtl/hfa/top_module.v
-top hc_verify_top
rtl/pkg_verify.sv
rtl/bus_if.sv
rtl/dup_a.v
rtl/dup_b.v
rtl/param_child.v
rtl/defparam_top.v
rtl/mid_anchor_depth.v
rtl/mid_arr.v
rtl/mid_md2d.v
rtl/mid_zigzag.v
rtl/mid_ifdef.v
rtl/mid_gen_soc.v
rtl/mid_gen_if.v
rtl/mid_param.v
rtl/inc_gate.v
rtl/ecc_engine.v
rtl/sub_bind.v
rtl/top_verify.v
rtl/ghost_soc.v