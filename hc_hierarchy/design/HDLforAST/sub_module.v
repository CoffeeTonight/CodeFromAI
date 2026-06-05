
module sub_module (
    input wire clk,
    input wire reset,
    output wire out
);
    reg out_reg;

    always @(posedge clk or posedge reset) begin
        if (reset)
            out_reg <= 1'b0;
        else
            out_reg <= ~out_reg;
    end

    assign out = out_reg;
endmodule
