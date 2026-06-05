module leaf_cell (
    input wire clk,
    input wire rst_n,
    output wire done
);
    assign done = clk & ~rst_n;
endmodule