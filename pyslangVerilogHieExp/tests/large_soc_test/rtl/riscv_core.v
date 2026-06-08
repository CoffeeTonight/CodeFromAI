module riscv_core #(
    parameter int CORE_ID = 0,
    parameter int NUM_IRQ = 32
)(
    input  logic clk,
    input  logic rst_n,
    input  logic [NUM_IRQ-1:0] irq
);
    // Simplified RISC-V core placeholder with generate for pipeline stages
    generate
        for (genvar s = 0; s < 5; s++) begin : gen_stage
            // pipeline stage
        end
    endgenerate
endmodule
