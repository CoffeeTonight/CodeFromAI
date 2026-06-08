// ===========================================
// Full-featured test filelist for rtl_dql
// Generated at 2026-06-01T11:03:57.159471
// ===========================================

// Basic include dir
+incdir+/home/user/tools/CodeFromAI/regexVerilogAST_v2/demo_data/synthetic_rtl_test/common_inc

// Global defines
+define+TOP_LEVEL_DEFINE
+define+DEBUG_MODE=1

// Environment variable test (parser should handle it)
+incdir+$RTL_ROOT/include

// Single library file (-v)
-v /home/user/tools/CodeFromAI/regexVerilogAST_v2/demo_data/synthetic_rtl_test/single_lib.v

// Library directory with extension
-y /home/user/tools/CodeFromAI/regexVerilogAST_v2/demo_data/synthetic_rtl_test/libs/tech_lib
+libext+.v+.sv

// Include all subsystems using -f and -F (mixed case for testing)
-f subsys_00.f
-F subsys_01.f
-f subsys_02.f
-F subsys_03.f
-f subsys_04.f
-F subsys_05.f
-f subsys_06.f
-F subsys_07.f
-f subsys_08.f
-F subsys_09.f

// Some relative paths
rtl/top_wrapper.v

// Comment test
# This is also a comment in some tools
// End of filelist

// Deeply nested filelist
-f nested/extra_blocks.f
