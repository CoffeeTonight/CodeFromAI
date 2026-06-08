module my_custom_cpu #(
    parameter int CORE_ID = 0,
    parameter int FEATURES = 3
)(
    input logic clk, rst_n
);
    generate
        if (FEATURES & 1) begin : gen_feature0
            // feature 0
        end
        if (FEATURES & 2) begin : gen_feature1
            // feature 1
        end
    endgenerate
endmodule
