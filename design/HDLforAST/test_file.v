
`include "middle_module.v"

module test_module (
    input wire clk,
    input wire reset,
    output wire [1:0] result
);
    middle_module u_middle (
        .clk(clk),
        .reset(reset),
        .out(result[0])
    );

    sub_module u_sub (
        .clk(clk),
        .reset(reset),
        .out(result[1])
    );

endmodule
