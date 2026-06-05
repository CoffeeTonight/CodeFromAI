`include "from_incdir_only.svh"
`include "include_only_mod.v"
module include_gateway (
    input  logic clk,
    input  logic rst_n,
    output logic inc_ok
);
    include_only_mod u_from_include (.clk(clk), .rst_n(rst_n), .active(inc_ok));
endmodule
