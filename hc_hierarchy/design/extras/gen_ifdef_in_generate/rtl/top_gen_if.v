// Golden: if (ENABLE) generate — only taken branch indexed when ENABLE=1
module top_gen_if (
    input wire clk
);
    generate
        if (ENABLE) begin : gen_on
            leaf u_on (.clk(clk));
        end else begin : gen_off
            leaf u_off (.clk(clk));
        end
    endgenerate
endmodule