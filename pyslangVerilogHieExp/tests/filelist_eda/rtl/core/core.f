// Core sub-system filelist
// Demonstrates:
// - +incdir relative to this file when used with -F
// - nested -F with correct relative paths from THIS file's location

+incdir+includes

cpu_core.sv

// Nested -F
-F ../bus/axi.f
