// Shared TB check-name width SSOT (avoid per-TB 64/96/128/255 drift).
`ifndef VERIF_TB_CHECK_VH
`define VERIF_TB_CHECK_VH

// Character capacity for check() / check_eq() string labels
`ifndef VERIF_TB_CHECK_NAME_CHARS
`define VERIF_TB_CHECK_NAME_CHARS 128
`endif

// Use: input [8*`VERIF_TB_CHECK_NAME_CHARS-1:0] name;

`endif
