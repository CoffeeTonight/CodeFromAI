
`include "sub_module.v"

module middle_module (
    input wire clk,
    input wire reset,
    output wire out
);
localparam TWO = 2;
    // 인스턴스화
    sub_module u_sub_0 #(.test(0.0), x(1+2*(1+TWO)+1), z(TWO)) (
        .clk(clk),
        .reset(reset),
        .out(out)
    );

    sub_module u_sub_1 (
        .clk(clk),
        .reset(reset),
        .out(out)
    );

    `ifndef USE_SUB_MODULE
        assign out = 1'b0; // 대체 로직
    `else
        `ifdef USE_SUB_MODULE
            sub_module u_sub_2 (
                .clk(clk),
                .reset(reset),
                .out(out)
            );
        `else
            assign out = 1'b1; // 또 다른 대체 로직
        `endif
    `endif
endmodule
