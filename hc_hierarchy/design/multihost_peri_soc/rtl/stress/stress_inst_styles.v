module stress_inst_styles (
    input  logic clk,
    input  logic rst_n
);
    uart16550 u_plain (.clk(clk), .rst_n(rst_n), .tx(), .rx(1'b0));
    uart16550 #(.FOO(8)) u_with_param (.clk(clk), .rst_n(rst_n), .tx(), .rx(1'b0));
    uart16550 u_array [0:1] (.clk(clk), .rst_n(rst_n), .tx(), .rx(1'b0));
    spi_master u_positional (clk, rst_n);
    i2c_controller u_named (.clk(clk), .rst_n(rst_n), .scl(), .sda());
    i3c_controller u_i3c_named (.clk(clk), .rst_n(rst_n), .scl(), .sda());
endmodule
