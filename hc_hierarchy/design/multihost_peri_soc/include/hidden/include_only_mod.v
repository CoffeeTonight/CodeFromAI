// Included from include_gateway.v — intentionally absent from all .f lists
module include_only_mod (
    input  logic clk,
    input  logic rst_n,
    output logic active
);
    assign active = clk & rst_n;
endmodule
