// =============================================================================
// Top-level EDA-style filelist for comprehensive parser testing
// This file exercises almost all common patterns used in real SoC projects
// =============================================================================

// --- Comments of various styles ---
# shell-style comment (some tools support this)
// C++ style comment
/* multi-line
   comment
   spanning lines */

// --- Environment variable usage (parser must handle these) ---
$PROJ_ROOT/tests/filelist_eda
${PROJ_ROOT}/tests/filelist_eda

// --- Include directories (multiple, order matters) ---
+incdir+includes
+incdir+rtl/core/includes

// --- Main design files using -F (correct relative path handling) ---
-F rtl/core/core.f

// Bare source file (normal usage)
tb/tb_top.sv

// --- Library search ( -y + +libext ) ---
-y ip_libs/stdcell
+libext+.v+.sv

// --- Single library file (-v) ---
-v libfiles/memory_lib.v
