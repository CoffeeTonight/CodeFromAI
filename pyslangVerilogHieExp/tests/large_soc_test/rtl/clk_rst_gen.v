module clk_rst_gen #(
    parameter int NUM_DOMAINS = 4
)(
    input  logic clk_in,
    input  logic rst_n_in,
    output logic [NUM_DOMAINS-1:0] clk_out,
    output logic [NUM_DOMAINS-1:0] rst_n_out
);
    generate
        for (genvar i = 0; i < NUM_DOMAINS; i++) begin : gen_domain
            assign clk_out[i] = clk_in; // simplified
            assign rst_n_out[i] = rst_n_in;
        end
    endgenerate
endmodule
