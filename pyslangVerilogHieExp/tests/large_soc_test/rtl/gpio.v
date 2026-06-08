module gpio #(
    parameter int ID = 0,
    parameter int WIDTH = 32
)(
    input  logic clk,
    input  logic rst_n,
    // ... typical peripheral ports ...
    input  logic [31:0] paddr,
    input  logic        pwrite,
    input  logic [31:0] pwdata,
    output logic [31:0] prdata
);
    // Simplified with some generate for register banks
    generate
        for (genvar r = 0; r < 8; r++) begin : gen_reg
            // register
        end
    endgenerate
endmodule
