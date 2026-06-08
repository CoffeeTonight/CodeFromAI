// Core CPU module
`include "cpu_pkg.svh"

module cpu_core #(
    parameter int WIDTH = cpu_pkg::CORE_WIDTH
)(
    input  logic clk,
    input  logic rst_n,
    output logic [WIDTH-1:0] result
);
    // Simple logic
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            result <= '0;
        else
            result <= result + 1;
    end
endmodule
