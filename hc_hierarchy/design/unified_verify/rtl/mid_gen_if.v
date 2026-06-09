// gen_ifdef_in_generate: if (ENABLE) generate with +define+ENABLE
module mid_gen_if (
    input logic clk,
    input logic rst_n
);
    generate
        if (ENABLE) begin : gen_on
            leaf_cell u_on (.clk(clk), .rst_n(rst_n), .done());
        end else begin : gen_off
            leaf_cell u_off (.clk(clk), .rst_n(rst_n), .done());
        end
    endgenerate
endmodule