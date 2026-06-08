module ahb_to_apb_bridge #(
    parameter int NUM_APB = 4
)(input logic clk, rst_n);
    generate
        for (genvar i = 0; i < NUM_APB; i++) begin : gen_apb
            // per-apb logic
        end
    endgenerate
endmodule
