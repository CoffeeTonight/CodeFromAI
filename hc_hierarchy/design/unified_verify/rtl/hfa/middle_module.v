
`include "sub_module.v"

module middle_module #(parameter ONE=1)(
      clk,
      reset,
      out
);
localparam TWO = 2;

    input wire clk;
    input wire reset;
    output wire out;

    sub_module u_subTop_0 #(.test(0.0), x(1+2*(1+TWO)+1), z(TWO)) (
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
        assign out = 1'b0;
    `else
        `ifdef USE_SUB_MODULE
            sub_module u_sub_2 (
                .clk(clk),
                .reset(reset),
                .out(out)
            );
        `else
            assign out = 1'b1;
        `endif
    `endif
endmodule