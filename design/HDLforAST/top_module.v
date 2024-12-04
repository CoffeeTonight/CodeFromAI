
`include "middle_module.v"
module top_a ();
    middle_module u_middle_0 (
        .clk(clk),
        .reset(reset),
        .out(out[0])
    ); endmodule
module top_module (
    input wire clk, ck
               , clock,
    input wire reset,
    input a,
    input b_reg,
    buf buf,
    inout IO,
    input [1:0][2:0][3:0] m_i,
    output [2:0][1:0][7:0] m_o,
    output reg [3:0] out
);
    // Parameterized instance
    middle_module u_middle_0 (
        .clk(clk),
        .reset(reset),
        .out(out[0])
    );

    middle_module
    `ifdef USE_M1
        u_middle_1 
    `else
        `ifdef UPPER
        u_middle_A
        `elsif SPC
        u_middle__
        `else
        u_middle_a
        `endif 
    `endif
    (
        .clk(clk),
        .reset(reset),
        .out(out[1])
    );

    `ifdef USE_MIDDLE_MODULE
        middle_module u_middle_2 (
            .clk(clk),
            .reset(reset),
            .out(out[2])
        );
    `else
        assign out[2] = 1'b0; // 대체 로직
    `endif

    assign out[3] = 1'b1; // 항상 1
endmodule
