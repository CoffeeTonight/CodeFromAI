// Bus size (byte count 1/2/4) ↔ AMBA wire encodings
// Include after verif_bus_defs.vh; call `VERIF_BUS_SIZE_FUNCS inside module.
`ifndef VERIF_BUS_SIZE_HELPERS_VH
`define VERIF_BUS_SIZE_HELPERS_VH

`define VERIF_BUS_SIZE_FUNCS \
  function [2:0] bus_hsize_for_bytes; \
    input [2:0] sz; \
    begin \
      case (sz) \
        3'd1: bus_hsize_for_bytes = 3'b000; \
        3'd2: bus_hsize_for_bytes = 3'b001; \
        default: bus_hsize_for_bytes = 3'b010; \
      endcase \
    end \
  endfunction \
  function [2:0] bus_axsize_for_bytes; \
    input [2:0] sz; \
    begin \
      case (sz) \
        3'd1: bus_axsize_for_bytes = 3'b000; \
        3'd2: bus_axsize_for_bytes = 3'b001; \
        default: bus_axsize_for_bytes = 3'b010; \
      endcase \
    end \
  endfunction \
  function [2:0] bus_hsize_to_bytes; \
    input [2:0] hsize; \
    begin \
      case (hsize) \
        3'd0: bus_hsize_to_bytes = 3'd1; \
        3'd1: bus_hsize_to_bytes = 3'd2; \
        default: bus_hsize_to_bytes = 3'd4; \
      endcase \
    end \
  endfunction

// Aliases so existing call sites can migrate: hsize_for_bytes → bus_hsize_for_bytes
`define VERIF_BUS_SIZE_FUNCS_COMPAT \
  `VERIF_BUS_SIZE_FUNCS \
  function [2:0] hsize_for_bytes; \
    input [2:0] sz; \
    begin hsize_for_bytes = bus_hsize_for_bytes(sz); end \
  endfunction \
  function [2:0] axsize_for_bytes; \
    input [2:0] sz; \
    begin axsize_for_bytes = bus_axsize_for_bytes(sz); end \
  endfunction

`endif
