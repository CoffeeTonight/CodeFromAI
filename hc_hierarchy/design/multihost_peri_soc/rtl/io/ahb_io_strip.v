module ahb_io_strip (
    input  logic clk,
    input  logic rst_n
);
    ahb_fabric  u_ahb (.clk(clk), .rst_n(rst_n));
    uart16550   u_uart_dbg (.clk(clk), .rst_n(rst_n), .tx(), .rx(1'b0));
    gpio_bank   u_gpio_dbg (.clk(clk), .rst_n(rst_n), .pad());
endmodule
