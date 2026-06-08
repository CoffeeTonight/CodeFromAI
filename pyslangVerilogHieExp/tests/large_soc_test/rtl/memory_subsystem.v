module memory_subsystem #(
    parameter int NUM_SRAM = 4
)(
    input logic clk, rst_n
);
    generate
        for (genvar s = 0; s < NUM_SRAM; s++) begin : gen_sram
            sram_ctrl #(.MEM_SIZE(4096 * (s+1))) u_sram (.clk(clk), .rst_n(rst_n));
        end
    endgenerate
    ddr_ctrl_stub u_ddr (.clk(clk), .rst_n(rst_n));
endmodule
