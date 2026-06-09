module leaf_cell (
    input  logic clk,
    input  logic rst_n,
    output logic done
);
    assign done = clk & rst_n;
endmodule