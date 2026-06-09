module apb_periph_cluster (
    input  logic clk,
    input  logic rst_n
);
    uart16550       u_uart0 (.clk(clk), .rst_n(rst_n), .tx(), .rx(1'b0));
    uart16550       u_uart1 (.clk(clk), .rst_n(rst_n), .tx(), .rx(1'b0));
    spi_master      u_spi0  (.clk(clk), .rst_n(rst_n), .sck(), .mosi(), .miso(1'b0));
    spi_master      u_spi1  (.clk(clk), .rst_n(rst_n), .sck(), .mosi(), .miso(1'b0));
    spi_slave       u_spi_s (.clk(clk), .rst_n(rst_n), .sck(1'b0), .mosi(1'b0), .miso());
    i2c_controller  u_i2c0  (.clk(clk), .rst_n(rst_n), .scl(), .sda());
    i3c_controller  u_i3c0  (.clk(clk), .rst_n(rst_n), .scl(), .sda());
    gpio_bank       u_gpio0 (.clk(clk), .rst_n(rst_n), .pad());
    pwm_block       u_pwm0  (.clk(clk), .rst_n(rst_n), .pwm_out());
    can_fd_ctrl     u_can0  (.clk(clk), .rst_n(rst_n), .can_rx(1'b0), .can_tx());
endmodule
