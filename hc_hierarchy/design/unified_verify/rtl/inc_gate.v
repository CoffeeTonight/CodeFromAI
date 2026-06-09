// multihost-style: module only reachable via `include (not in filelist)
`include "inc_only.v"

module inc_gate (
    input  logic clk,
    input  logic rst_n
);
    inc_only_mod u_inc (.clk(clk), .rst_n(rst_n), .active());
endmodule