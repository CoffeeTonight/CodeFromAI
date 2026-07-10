// Simulation timeout — include once per testbench top module.
`ifndef VERIF_SIM_WATCHDOG_VH
`define VERIF_SIM_WATCHDOG_VH

`ifndef VERIF_SIM_TIMEOUT_NS
  `define VERIF_SIM_TIMEOUT_NS 20000000
`endif

`define VERIF_SIM_WATCHDOG_NS \
  initial begin \
    #( `VERIF_SIM_TIMEOUT_NS ); \
    $fatal(1, "[sim] TIMEOUT after %0d ns — firmware hang or missing $finish", \
           `VERIF_SIM_TIMEOUT_NS); \
  end

`endif